# Themes

A theme is three seed colours: `bg`, `fg` and `accent`. Everything else is derived:

| Tokens                                               | Derived as                                                                                                                               |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `BG_DEEP`, `BLACK`                                   | `bg` pushed _away_ from `fg` (toward black on dark themes, white on light)                                                               |
| `BG_ALT`, `UI`, `UI_ALT`, `UI_HI`, `MUTED`, `FG_ALT` | steps from `bg` toward `fg` (6 %, 13 %, 19 %, 31 %, 56 %, 82 %; the first four ×1.6 on light themes, where thin grey lines read fainter) |
| `ACCENT_1` … `ACCENT_8`                              | steps from `accent` toward `bg` (17 % … 96 %): the accent ramp                                                                           |
| `ACCENT_HI`                                          | `accent` 28 % toward `fg` (more emphasis)                                                                                                |

The `fireproof` preset pins every token to its original hand-picked value, so its ramp is not
perfectly monotonic (`ACCENT_3` and `ACCENT_4` are near-equal in lightness). Derived themes are
strictly monotonic. Only fireproof's exact seeds get the pinned table; any other seeds are
derived, so moving one seed by a single unit away from fireproof shifts the accent ramp by up
to 21 units. Nothing in a design may depend on the pinned values.

Designs only use these tokens (plus `mix()`, `ramp()`, `ladder()` and `by_regime()` of them),
so every design renders in any theme. The tokens are symbolic: a design never sees their hex
values, and they resolve only when the tools write the SVG under a theme. The one constant
colours, `MASK_WHITE` and `MASK_BLACK`, paint only inside masks.

Every command that renders takes `--theme` (default `$WALLDYE_THEME`, else fireproof): a preset
name or `bg-fg-accent` hex seeds, 3 or 6 digits each, `#` optional. `bg,fg,accent` and
`bg=..,fg=..,accent=..` also work. There are no per-token or preset overrides.

```bash
uv run walldye preview <slug> --theme nord
uv run walldye preview <slug> --theme 1e1e2e-cdd6f4-fab387
uv run walldye themes                     # presets, their seeds and regime
uv run walldye themes --theme nord        # also that theme's 21 tokens
```

## Presets

| Preset                | bg        | fg        | accent                                    |
| --------------------- | --------- | --------- | ----------------------------------------- |
| `fireproof` (default) | `#1C1B1A` | `#DAD8CE` | `#CF6A4C` (all 21 tokens pinned by hand)  |
| `flexoki-light`       | `#FFFCF0` | `#100F0F` | `#BC5215`                                 |
| `gruvbox-dark`        | `#282828` | `#EBDBB2` | `#FE8019`                                 |
| `nord`                | `#2E3440` | `#ECEFF4` | `#88C0D0`                                 |
| `catppuccin-mocha`    | `#1E1E2E` | `#CDD6F4` | `#CBA6F7`                                 |
| `tokyo-night`         | `#1A1B26` | `#C0CAF5` | `#7AA2F7`                                 |
| `rose-pine`           | `#191724` | `#E0DEF4` | `#EBBCBA`                                 |
| `everforest-dark`     | `#2D353B` | `#D3C6AA` | `#A7C080`                                 |
| `ayu-dark`            | `#0B0E14` | `#BFBDB6` | `#E6B450`                                 |
| `dracula`             | `#282A36` | `#F8F8F2` | `#FF79C6`                                 |
| `solarized-light`     | `#FDF6E3` | `#586E75` | `#CB4B16`                                 |

If the user names a known scheme that is not a preset (Kanagawa, One Dark…),
use its published background, foreground and signature accent as seeds.

## Regimes and the light ladder

A theme is in the light regime when its bg is strictly brighter than its fg (WCAG luminance;
a tie counts as dark). A design is drawn once per regime, and `s.light` says which one; it is
the only theme fact a design can read. Build keeps one template per aspect, written under
fireproof, adds a `.light.svg` written under flexoki-light only where the light drawing
differs, and fits how every colour in them moves with the seeds. Within a regime the geometry
cannot change with the theme; between regimes it may, at a cost.

Tokens invert on light themes: greys walk toward a dark fg, the accent ramp fades toward a
pale bg, and `BLACK`/`BG_DEEP` become the palest "beyond the page" tones. A design whose drama
relied on a near-black void (shadows, space scenes) can go flat on paper white. When the light
render needs help, climb this ladder and stop at the first step that works:

1. Tokens only. Most designs need nothing more. Check `--theme flexoki-light` and
   `--theme solarized-light` anyway.
2. A per-regime colour: `STRUCT = by_regime(UI, MUTED)` (the dark colour first), or lifting a
   whole set of roles one step, as examples/glyph-terrain.py does with
   `by_regime(STEPS[k], STEPS[k + 1])`. The drawing stays the same, so one template serves
   both regimes.
3. A geometry branch under `if s.light:` (examples/dither-moon.py inks its shadows instead
   of its highlights). Build then writes a `.light.svg` for every native aspect and variant,
   so the piece has twice the templates to build, commit and keep correct.
4. `themes: [dark]` in meta.yaml, only after steps 2 and 3 were tried, with the reason in
   `notes` in plain words. Under light seeds the site then shows the piece with the visitor's
   bg and fg swapped and a caption saying it was made for dark themes.

`walldye preview` prints `regime: dark|light` and `light geometry: same as dark` or
`differs from dark`, so every preview says whether a design is on step 3.
