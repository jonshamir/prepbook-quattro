# Prepbook Quattro

Modified version of iA Writer Quattro with custom glyph spacing and rebuilt fraction glyphs for [Prepbook](https://prepbook.app/).

Derived from [iA Writer Quattro](https://github.com/iaolo/iA-Fonts) under the SIL Open Font License 1.1. Renamed per OFL requirements (Reserved Font Name "iA Writer" replaced).

## What it does
- Tightens punctuation spacing (period, comma, quotes, parens, brackets, braces, `!`, `|`, space) using the font's existing width classes.
- Rebuilds the precomposed fraction glyphs (½, ¼, ¾, ⅓, ⅔, ⅕, …) as wider composites of `<digit>.numr` + `fraction` + `<digit>.dnom` with a single continuous slash.
- Reshapes the `fraction` glyph (U+2044) itself from two disjoint parallelograms into one continuous slash, while preserving the weight-axis gvar deltas so bold still works.
- Renames the family to "Prepbook Quattro" in all name table records.

## Setup

```
python3 -m venv .venv
.venv/bin/pip install fonttools
```

## Usage

### 1. Add source fonts

Copy the iA Writer Quattro **variable** `.ttf` files into `input/`:

```
input/
  iAWriterQuattroV.ttf          (Variable Roman)
  iAWriterQuattroV-Italic.ttf   (Variable Italic)
```

Download from: https://github.com/iaolo/iA-Fonts/tree/master/iA%20Writer%20Quattro/Variable

### 2. Inspect current widths

```
.venv/bin/python -P scripts/inspect_font.py
```

This dumps the width classes, punctuation metrics, and fraction glyph structure for every `.ttf` in `input/`. Use it before and after building.

> **Why `-P`?** The flag disables prepending the script's directory to `sys.path`, which otherwise shadows stdlib modules in some Python 3.14 setups.

### 3. Edit `config.json`

Key sections:
- `allowed_widths` — the safety rail. Every value assigned in `modifications` must be one of these four canonical width classes.
- `modifications` — glyph name → new advance width.
- `fraction_rebuild` — configures the composite fraction pass. `layout.gap` widens or tightens the fractions; set `reshape_fraction_slash: true` to also rewrite the `fraction` glyph itself into one continuous slash.

### 4. Build

```
.venv/bin/python -P scripts/build.py
```

Modified fonts appear in `output/`.

### 5. Verify

```
.venv/bin/python -P scripts/inspect_font.py output/PrepbookQuattroV.ttf output/PrepbookQuattroV-Italic.ttf
```

## File structure

```
prepbook-quattro/
├── config.json           # Width modifications, fraction rebuild config, family name
├── input/                # Source iA Writer Quattro variable TTFs (git-ignored)
├── output/               # Built Prepbook Quattro fonts (git-ignored)
├── scripts/
│   ├── inspect_font.py   # Dump width classes, glyph metrics, fraction structure
│   └── build.py          # Apply modifications, rebuild fractions, rename
├── CLAUDE.md             # Architecture notes for AI-assisted edits
└── README.md
```

## Notes
- Glyph outlines are never drawn. The build only edits `hmtx`, writes composite glyph records, and repositions the 8 existing points of the `fraction` glyph (preserving gvar deltas for weight variation).
- After a build, run `inspect_font.py` on the outputs to verify advance widths and confirm each precomposed fraction is now a composite referencing `<digit>.numr`, `fraction`, and `<digit>.dnom`.
- The build prints a warning about outlier source widths (550, 598, 750, etc.) on precomposed accent glyphs — these are iA's own artifacts, harmless, and not part of the canonical 4-width architecture.

## License
SIL Open Font License 1.1 — see LICENSE.md in the source repository.
