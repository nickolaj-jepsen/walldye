# Font sources

`uv run scripts/fonts/subset.py` writes the subsets to `src/assets/fonts/` from the two TTFs and the
zip below, checked against their sha256; it refuses to run while a pin in its `SOURCES` is missing
here. The other rows record provenance.

## EB Garamond 1.003

google/fonts at commit `f8c1d3d6cc75e30d77130bdcbfbff27e3b6233fe` ("bump version to 1.003", 2026-06-17).
Copyright 2017 The EB Garamond Project Authors. SIL OFL 1.1, no Reserved Font Name.

| File | sha256 |
|---|---|
| [EBGaramond[wght].ttf](https://raw.githubusercontent.com/google/fonts/f8c1d3d6cc75e30d77130bdcbfbff27e3b6233fe/ofl/ebgaramond/EBGaramond%5Bwght%5D.ttf) | `ef9512f92f6d579e5dc75af59a5a4b1b8b47d2eda89e00b954d44520e5369027` |
| [EBGaramond-Italic[wght].ttf](https://raw.githubusercontent.com/google/fonts/f8c1d3d6cc75e30d77130bdcbfbff27e3b6233fe/ofl/ebgaramond/EBGaramond-Italic%5Bwght%5D.ttf) | `bba2c4499c93c9612b90b9825d32b07da52fce2fe57562a1eb6b833553f93c4e` |
| [OFL.txt](https://raw.githubusercontent.com/google/fonts/f8c1d3d6cc75e30d77130bdcbfbff27e3b6233fe/ofl/ebgaramond/OFL.txt) | `0985066662eb755ed3683ae5482a81a9195b49ce3f7e165cc2388b3dbece7dd7` |

Output: `eb-garamond-roman.woff2`, `eb-garamond-italic.woff2`.

## Monaspace Krypton 1.400

githubnext/monaspace release [v1.400](https://github.com/githubnext/monaspace/releases/tag/v1.400)
(tag commit `f31794b6e9e65698a062262e2f826f679dcb7070`, 2026-03-28).
Copyright (c) 2023, GitHub. SIL OFL 1.1 with Reserved Font Names "Monaspace", "Argon", "Neon",
"Xenon", "Radon" and "Krypton".

| File | sha256 |
|---|---|
| [monaspace-variable-v1.400.zip](https://github.com/githubnext/monaspace/releases/download/v1.400/monaspace-variable-v1.400.zip) | `b69a7f2a3c455c89dcb6cc23b61bb3fb8beecba728ccdebeccd80577e58de0c8` |
| `Variable Fonts/Monaspace Krypton/Monaspace Krypton Var.ttf` (in the zip) | `6462cae55b336ae6ffb7c8f1932177960510a4207e65803f527b276d42c8a240` |
| [LICENSE](https://raw.githubusercontent.com/githubnext/monaspace/v1.400/LICENSE) | `0e84e5f7dd6f05e74a00f2fb828ca43e489d954f5509ff0fa439ea18c0d35fe9` |

Output: `walldye-mono.woff2`. A subset is a Modified Version under the OFL, so it cannot use the
Reserved Font Names: the family is renamed "Walldye Mono", keeping the upstream copyright notice
as name ID 0.

## Subsetting

The site subsets its own because the Fontsource and Google latin subsets of EB Garamond lack
smcp, c2sc, onum and U+2197. `sups` is left out: it costs about 19 kB per Garamond face for one
footnote marker. The ranges and features are `UNICODES` and `FEATURES` in `subset.py`.

## License text

`src/assets/fonts/OFL.txt` holds both copyright notices and the license.
`LICENSES/OFL-1.1.txt` is the SPDX text
([spdx/license-list-data `b8d6af45ad2fcfed61bb85a8ad068aa4a77eadf9`](https://raw.githubusercontent.com/spdx/license-list-data/b8d6af45ad2fcfed61bb85a8ad068aa4a77eadf9/text/OFL-1.1.txt)).
