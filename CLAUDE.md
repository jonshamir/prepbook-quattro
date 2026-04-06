# Prepbook Quattro - Font Modification Project

## What this is
A build pipeline that takes iA Writer Quattro variable fonts from `input/`, applies glyph width modifications defined in `config.json`, renames the family to "Prepbook Quattro", and outputs modified fonts to `output/`.

## Key constraints
- **Width classes are fixed.** iA Writer Quattro uses exactly 4 non-zero advance widths (discover them with `python scripts/inspect.py`). All modifications must use one of these widths — never introduce a new width value.
- **Only metrics change.** Glyph outlines are never modified. Changes are limited to the `hmtx` table (advance width + LSB).
- **HVAR is removed.** The build deletes the HVAR table from variable fonts to avoid stale interpolation deltas. The gvar table's phantom points handle weight-axis width changes.
- **OFL renaming.** The font must not use "iA Writer" in any name table record. The build script handles this.

## Workflow
1. Place source `.ttf` files in `input/`
2. `python scripts/inspect.py` — view all width classes and glyph metrics
3. Edit `config.json` — set desired glyph widths (must be from allowed_widths)
4. `python scripts/build.py` — produces renamed, modified fonts in `output/`
5. Run `inspect.py` on output fonts to verify

## Dependencies
- Python 3.8+
- `fonttools` (`pip install fonttools`)
