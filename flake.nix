{
  description = "walldye: procedural SVG wallpapers recoloured from three seed colours";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
    }:
    let
      inherit (nixpkgs) lib;
      forAllSystems =
        f: lib.genAttrs [ "x86_64-linux" "aarch64-linux" ] (system: f nixpkgs.legacyPackages.${system});

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      # Only what the Python package is built from, so a design or site edit doesn't rebuild it.
      packageSource = lib.fileset.toSource {
        root = ./.;
        fileset = lib.fileset.unions [
          ./pyproject.toml
          ./README.md
          ./LICENSE
          ./LICENSES
          ./walldye
        ];
      };
      withPackageSource = _final: prev: {
        walldye = prev.walldye.overrideAttrs { src = packageSource; };
      };

      # The wheels uv.lock pins, not nixpkgs' builds: renders match CI's only on the same versions.
      pythonSet =
        pkgs:
        (pkgs.callPackage pyproject-nix.build.packages { python = pkgs.python313; }).overrideScope (
          lib.composeManyExtensions [
            pyproject-build-systems.overlays.wheel
            (workspace.mkPyprojectOverlay { sourcePreference = "wheel"; })
            withPackageSource
          ]
        );

      # wallpapers/ without build output, which a `path:` flake would otherwise copy in.
      wallpapersIn =
        root:
        lib.cleanSourceWith {
          src = root;
          filter = path: type: !(type == "directory" && baseNameOf path == "build");
        };

      catalogue =
        pkgs:
        pkgs.runCommand "walldye-catalogue" { } ''
          mkdir $out
          cp -r ${wallpapersIn ./wallpapers} $out/wallpapers
          cp ${./taxonomy.yaml} $out/taxonomy.yaml
        '';

      # A wallpaper built from its own folder alone, so editing one piece rebuilds only its images.
      mkWallpaper =
        pkgs: venv:
        {
          slug,
          theme ? "fireproof",
          width ? 2560,
          height ? 1440,
          variant ? "default",
          set ? { },
        }:
        let
          piece = ./wallpapers + "/${slug}";
          root = pkgs.runCommand "walldye-${slug}-source" { } ''
            mkdir -p $out/wallpapers
            cp -r ${wallpapersIn piece} $out/wallpapers/${slug}
          '';
          themeArg =
            if builtins.isString theme then theme else "bg=${theme.bg},fg=${theme.fg},accent=${theme.accent}";
          w = toString width;
          h = toString height;
          args = [
            slug
            "--theme"
            themeArg
            "--aspect"
            "${w}x${h}"
            "--variant"
            variant
            "--fit"
          ]
          ++ lib.concatMap (k: [
            "--set"
            "${k}=${setValue set.${k}}"
          ]) (lib.attrNames set);
          setValue =
            v:
            if builtins.isBool v then
              lib.boolToString v
            else if v == null then
              "none"
            else
              toString v;
        in
        assert lib.assertMsg (builtins.pathExists piece) "walldye: no wallpaper named ${slug}";
        pkgs.runCommand "walldye-${slug}-${w}x${h}.png"
          {
            nativeBuildInputs = [ venv ];
            env.WALLDYE_ROOT = root;
          }
          ''
            walldye render ${lib.escapeShellArgs args} --width ${w} -o wall.png
            cp wall.png $out
          '';

      mkWalldye =
        pkgs:
        let
          venv = (pythonSet pkgs).mkVirtualEnv "walldye-env" workspace.deps.default;
          walldye =
            pkgs.runCommand "walldye-${(lib.importTOML ./pyproject.toml).project.version}"
              {
                nativeBuildInputs = [ pkgs.makeWrapper ];
                passthru.mkWallpaper = mkWallpaper pkgs venv;
                meta = {
                  description = "Procedural SVG wallpapers recoloured from three seed colours";
                  homepage = "https://walldye.com";
                  license = with lib.licenses; [
                    gpl3Plus
                    bsd2
                  ];
                  mainProgram = "walldye";
                };
              }
              ''
                makeWrapper ${venv}/bin/walldye $out/bin/walldye \
                  --set-default WALLDYE_ROOT ${catalogue pkgs}
              '';
        in
        walldye;
    in
    {
      packages = forAllSystems (pkgs: rec {
        walldye = mkWalldye pkgs;
        default = walldye;
      });

      overlays.default = final: _prev: { walldye = mkWalldye final; };

      checks = forAllSystems (
        pkgs:
        let
          inherit (self.packages.${pkgs.stdenv.hostPlatform.system}) walldye;
        in
        {
          inherit walldye;
          native = walldye.mkWallpaper {
            slug = "airfoil";
            theme = "nord";
            width = 3440;
            height = 1440;
          };
          fitted = walldye.mkWallpaper {
            slug = "arcs";
            theme = {
              bg = "#282828";
              fg = "#EBDBB2";
              accent = "#FE8019";
            };
            width = 1080;
            height = 2340;
          };
        }
      );

      devShells = forAllSystems (
        pkgs:
        let
          editable = (pythonSet pkgs).overrideScope (
            lib.composeManyExtensions [
              (workspace.mkEditablePyprojectOverlay { root = "$REPO_ROOT"; })
              withPackageSource
            ]
          );
          venv = editable.mkVirtualEnv "walldye-dev-env" workspace.deps.all;
        in
        {
          default = pkgs.mkShell {
            packages = [
              venv
              pkgs.uv
              pkgs.nodejs_24
              pkgs.pnpm
              pkgs.inkscape
            ];
            env = {
              # uv runs the Nix venv as is instead of syncing its own.
              UV_NO_SYNC = "1";
              UV_PYTHON = "${venv}/bin/python";
              UV_PROJECT_ENVIRONMENT = "${venv}";
              UV_PYTHON_DOWNLOADS = "never";
              UV_PYTHON_PREFERENCE = "only-system";
              # Its version must equal @playwright/test's in package.json.
              PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright-driver.browsers}";
              PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS = "true";
            };
            shellHook = ''
              unset PYTHONPATH
              export REPO_ROOT=$(git rev-parse --show-toplevel)
            '';
          };
        }
      );

      formatter = forAllSystems (pkgs: pkgs.nixfmt);
    };
}
