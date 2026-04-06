# Prepbook Quattro

Modified version of iA Writer Quattro with custom glyph spacing for [Prepbook](https://prepbook.app/).

Derived from [iA Writer Quattro](https://github.com/iaolo/iA-Fonts) under the SIL Open Font License 1.1. Renamed per OFL requirements (Reserved Font Name "iA Writer" replaced).

## Setup

```
pip install fonttools
```

## Usage

### 1. Add source fonts

Copy the iA Writer Quattro **variable** `.ttf` files into `input/`:

```
input/
  iAWriterQuattroS-Regular.ttf   (Variable Roman)
  iAWriterQuattroS-Italic.ttf    (Variable Italic)
```

Download from: https://github.com/iaolo/iA-Fonts/tree/master/iA%20Writer%20Quattro/Variable

### 2. Inspect current widths

```
python scripts/inspect.py
```

This shows all width classes in use and every punctuation glyph's current advance width. Use this to decide what to change.

### 3. Edit config.json

```json
{
  "family_name": "Prepbook Quattro",
  "allowed_widths": [600, 680, 780, 900],
  "modifications": {
    "period": 600,
    "comma": 600
  }
}
```

- **`allowed_widths`**: The fixed set of width classes Quattro uses. Run `inspect.py` to discover the actual values — only these widths are permitted.
- **`modifications`**: Map of glyph name → new advance width. Values must be in `allowed_widths`.

### 4. Build

```
python scripts/build.py
```

Modified fonts appear in `output/`.

## File structure

```
prepbook-quattro/
├── config.json          # Width modifications & family name
├── input/               # Source iA Writer Quattro variable TTFs (git-ignored)
├── output/              # Built Prepbook Quattro fonts
├── scripts/
│   ├── inspect.py       # Dump width classes & glyph metrics
│   └── build.py         # Apply modifications & rename
└── README.md
```

## Notes

- The build removes the `HVAR` table from variable fonts. The `gvar` phantom points still handle weight interpolation correctly for advance width changes.
- Glyph outlines are never modified — only horizontal metrics (`hmtx`) and metadata.
- After the first build, run `inspect.py` on the output fonts to verify changes.

## License

SIL Open Font License 1.1 — see LICENSE.md in the source repository.
