#!/usr/bin/env bash
# Runs a command with Playwright's browsers from the repo flake's nixpkgs (their version matches
# @playwright/test 1.63.0) and Mesa's EGL, which WebKit needs on a host without /run/opengl-driver.
# Usage: scripts/with-browsers.sh pnpm spike
set -euo pipefail
repo="$(cd "$(dirname "$0")/../.." && pwd)"
mapfile -t paths < <(nix build --no-link --print-out-paths --inputs-from "$repo" \
  nixpkgs#playwright-driver.browsers nixpkgs#mesa)
browsers="${paths[0]}"
mesa="${paths[1]}"
# A profile's LD_LIBRARY_PATH can pull in libraries built against another glibc.
unset LD_LIBRARY_PATH
export PLAYWRIGHT_BROWSERS_PATH="$browsers" PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true
export __EGL_VENDOR_LIBRARY_DIRS="$mesa/share/glvnd/egl_vendor.d" GBM_BACKENDS_PATH="$mesa/lib/gbm"
export LIBGL_DRIVERS_PATH="$mesa/lib/dri" LIBGL_ALWAYS_SOFTWARE=1
exec "$@"
