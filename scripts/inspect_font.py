#!/usr/bin/env python3
"""Inspect unique advance widths in iA Writer Quattro variable fonts.

Usage:
    python scripts/inspect.py                     # auto-finds fonts in input/
    python scripts/inspect.py path/to/font.ttf    # inspect specific file
"""
import sys, os, json
from collections import defaultdict
from fontTools.ttLib import TTFont

PUNCT_GLYPHS = [
    "period", "comma", "colon", "semicolon", "exclam", "question",
    "hyphen", "endash", "emdash", "parenleft", "parenright",
    "bracketleft", "bracketright", "braceleft", "braceright",
    "slash", "backslash", "at", "ampersand", "asterisk", "percent",
    "numbersign", "dollar", "plus", "equal", "less", "greater",
    "quotedbl", "quotesingle", "quotedblleft", "quotedblright",
    "quoteright", "quoteleft", "ellipsis", "bullet",
    "guillemotleft", "guillemotright", "underscore", "bar",
    "asciitilde", "asciicircum", "grave",
]


def inspect(path: str):
    font = TTFont(path)
    hmtx = font["hmtx"]

    width_groups: dict[int, list[str]] = defaultdict(list)
    for name, (w, _lsb) in hmtx.metrics.items():
        width_groups[w].append(name)

    print(f"\n{'='*64}")
    print(f"  {os.path.basename(path)}")
    print(f"  UPM: {font['head'].unitsPerEm}  |  Glyphs: {len(hmtx.metrics)}  |  Unique widths: {len(width_groups)}")
    print(f"  HVAR: {'yes' if 'HVAR' in font else 'no'}  |  gvar: {'yes' if 'gvar' in font else 'no'}  |  isFixedPitch: {font['post'].isFixedPitch}")
    print(f"{'='*64}")

    print("\n  WIDTH CLASSES:")
    for w in sorted(width_groups.keys()):
        glyphs = sorted(width_groups[w])
        print(f"\n  {w} units  ({len(glyphs)} glyphs)")
        # Show up to 50
        for i in range(0, min(len(glyphs), 50), 10):
            chunk = glyphs[i:i+10]
            print(f"    {', '.join(chunk)}")
        if len(glyphs) > 50:
            print(f"    ... and {len(glyphs) - 50} more")

    # Fractions: show composite structure if rebuilt
    FRACTION_CODEPOINTS = [
        (0x00BC, "1/4"), (0x00BD, "1/2"), (0x00BE, "3/4"),
        (0x2150, "1/7"), (0x2151, "1/9"), (0x2152, "1/10"),
        (0x2153, "1/3"), (0x2154, "2/3"),
        (0x2155, "1/5"), (0x2156, "2/5"), (0x2157, "3/5"), (0x2158, "4/5"),
        (0x2159, "1/6"), (0x215A, "5/6"),
        (0x215B, "1/8"), (0x215C, "3/8"), (0x215D, "5/8"), (0x215E, "7/8"),
    ]
    glyf = font.get("glyf")
    cmap = font.getBestCmap()
    print(f"\n  FRACTIONS:")
    for cp, label in FRACTION_CODEPOINTS:
        if cp not in cmap:
            continue
        gname = cmap[cp]
        w, lsb = hmtx.metrics[gname]
        kind = "?"
        detail = ""
        if glyf and gname in glyf:
            g = glyf[gname]
            if g.numberOfContours == -1:
                kind = "composite"
                comps = ", ".join(c.glyphName for c in g.components)
                detail = f"  [{comps}]"
            else:
                kind = "simple"
                detail = f"  contours={g.numberOfContours}"
        print(f"    U+{cp:04X} {label:5s} {gname:20s}  width={w:4d}  lsb={lsb:5d}  {kind}{detail}")

    print(f"\n  PUNCTUATION & SYMBOLS:")
    for name in PUNCT_GLYPHS:
        if name in hmtx.metrics:
            w, lsb = hmtx.metrics[name]
            print(f"    {name:24s}  width={w:4d}  lsb={lsb:4d}")
        else:
            print(f"    {name:24s}  (not in font)")

    font.close()


def find_fonts(directory: str) -> list[str]:
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.lower().endswith(".ttf")
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        paths = sys.argv[1:]
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(script_dir)
        paths = find_fonts(os.path.join(project_dir, "input"))
        if not paths:
            print("No .ttf files found in input/. Pass font paths as arguments or place them in input/.")
            sys.exit(1)

    for p in paths:
        inspect(p)
