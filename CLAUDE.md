# Prepbook Quattro - Font Modification Project

## What this is
A build pipeline that takes iA Writer Quattro variable fonts from `input/`, applies modifications defined in `config.json` (per-glyph advance widths + a fraction rebuild pass), renames the family to "Prepbook Quattro", and outputs the result to `output/`.

## Key constraints
- **Canonical width classes are fixed.** iA Writer Quattro is built around four advance-width classes: **300, 450, 600, 900**. (The source also contains a handful of outlier widths on precomposed accent glyphs — 25, 26, 105, 134–137, 550, 598, 750, 903, 1200 — which are artifacts, not part of the architecture.) Any value written to `modifications` in `config.json` must be one of the four canonical widths — never introduce a new width. Discover the actual widths with `inspect_font.py`.
- **No new outlines.** Glyph splines are never drawn. Changes are limited to:
  - **`hmtx`** — advance width + LSB updates
  - **`glyf` composite rebuilds** — new composite glyph records that reference existing component glyphs (used by the fraction rebuild: precomposed fractions become composites of `<digit>.numr` + `fraction` + `<digit>.dnom`)
  - **`glyf` point repositioning on the `fraction` glyph only** — its 8 original points (2 contours × 4) are kept at the same indices but repositioned into one continuous slash. Original `gvar` deltas are retained so weight-axis variation still works; the pair of coincident seam points get their deltas averaged ("welded") so the seam stays closed across the axis.
- **HVAR.** If present, it's deleted. `gvar`'s phantom points handle weight-axis width changes. (In the current source HVAR is already absent — the removal is a no-op on these files.)
- **OFL renaming.** The font must not use "iA Writer" in any name table record. `build.py` handles this.

## Workflow
1. Place source `.ttf` files in `input/` (iA Writer Quattro Variable Roman + Italic).
2. `.venv/bin/python -P scripts/inspect_font.py` — view width classes, punctuation widths, and fraction glyph structure.
3. Edit `config.json` — adjust `modifications`, `fraction_rebuild.layout.gap`, etc.
4. `.venv/bin/python -P scripts/build.py` — produces renamed, modified fonts in `output/`.
5. Re-run `inspect_font.py` on the output fonts to verify.

## Dependencies
- Python 3.8+ (tested with Python 3.14 in a local `.venv/`)
- `fonttools` — `.venv/bin/pip install fonttools`

## Python invocation note
The script is run with `python -P` to prevent its directory from being prepended to `sys.path`. Without `-P`, a script named `inspect.py` (the old name) shadows stdlib `inspect` and breaks `dataclasses` import on Python 3.14. The script has since been renamed to `inspect_font.py`, but `-P` is still the safest invocation.
