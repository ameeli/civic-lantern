# Self-hosted fonts

These `.woff2` files are vendored copies of Google Fonts, loaded via
`next/font/local` in `src/app/layout.tsx` instead of `next/font/google`.

**Why:** `next/font/google` fetches font files from Google's servers at
*build* time via Turbopack. That build-time network dependency has caused
repeated build failures (both in CI and on Vercel) with a
`Module not found: Can't resolve '@vercel/turbopack-next/internal/font/google/font'`
error, specifically when a font is requested with multiple weights.
Self-hosting removes the network dependency entirely — nothing is fetched
from Google at build or run time.

All fonts here are licensed under the [SIL Open Font License](https://openfontlicense.org/),
which permits redistribution/bundling. Latin subset only, matching what the
app actually uses.

| File | Family | Weight(s) | Style | Source |
|---|---|---|---|---|
| `inconsolata-latin-wght-normal.woff2` | Inconsolata | 300–600 (variable) | normal | fonts.google.com/specimen/Inconsolata |
| `eagle-lake-latin-400-normal.woff2` | Eagle Lake | 400 | normal | fonts.google.com/specimen/Eagle+Lake |
| `playfair-display-latin-wght-normal.woff2` | Playfair Display | 400–800 (variable) | normal | fonts.google.com/specimen/Playfair+Display |
| `playfair-display-latin-wght-italic.woff2` | Playfair Display | 400–800 (variable) | italic | fonts.google.com/specimen/Playfair+Display |

To update a font (e.g. add a subset or weight), fetch the CSS from
`https://fonts.googleapis.com/css2?family=<Family>:wght@<range>&display=swap`
with a modern browser User-Agent (to get `woff2` URLs), download the
`.woff2` file(s) for the subset(s) you need, and update `layout.tsx`
accordingly.
