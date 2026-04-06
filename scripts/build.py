#!/usr/bin/env python3
"""Build Prepbook Quattro from iA Writer Quattro variable fonts.

Reads config.json for glyph width modifications and family name,
applies changes to all .ttf files in input/, writes results to output/.

Usage:
    python scripts/build.py
    python scripts/build.py --config custom-config.json
"""
import sys, os, json, argparse, shutil
from fontTools.ttLib import TTFont


def load_config(path: str) -> dict:
    with open(path) as f:
        cfg = json.load(f)
    required = ["family_name", "allowed_widths", "modifications"]
    for key in required:
        if key not in cfg:
            raise ValueError(f"Missing required key '{key}' in config")
    return cfg


def get_allowed_widths_from_font(font: TTFont) -> set[int]:
    """Extract the set of unique advance widths actually used in the font."""
    hmtx = font["hmtx"]
    return set(w for w, _lsb in hmtx.metrics.values())


def rename_font(font: TTFont, new_family: str, old_family: str = "iA Writer Quattro"):
    """Replace family name in all relevant name table records."""
    name_table = font["name"]
    for record in name_table.names:
        text = record.toUnicode()
        if old_family in text:
            new_text = text.replace(old_family, new_family)
            name_table.setName(
                new_text,
                record.nameID,
                record.platformID,
                record.platEncID,
                record.langID,
            )
        # Also catch variations like "iAWriterQuattro" (PostScript name)
        old_ps = old_family.replace(" ", "")
        new_ps = new_family.replace(" ", "")
        text = record.toUnicode()
        if old_ps in text:
            new_text = text.replace(old_ps, new_ps)
            name_table.setName(
                new_text,
                record.nameID,
                record.platformID,
                record.platEncID,
                record.langID,
            )


def apply_modifications(font: TTFont, modifications: dict[str, int], allowed_widths: list[int]):
    """Change advance widths for specified glyphs, re-centering the ink."""
    hmtx = font["hmtx"]
    glyf = font.get("glyf")  # None for CFF fonts
    allowed = set(allowed_widths)
    changed = []

    for glyph_name, new_width in modifications.items():
        if glyph_name.startswith("_"):
            continue  # skip comment keys

        if new_width not in allowed:
            raise ValueError(
                f"Width {new_width} for '{glyph_name}' is not in allowed_widths {sorted(allowed)}. "
                f"Quattro uses a fixed set of width classes — pick one of those."
            )

        if glyph_name not in hmtx.metrics:
            print(f"  WARNING: glyph '{glyph_name}' not found in font, skipping")
            continue

        old_width, old_lsb = hmtx.metrics[glyph_name]
        if old_width == new_width:
            continue

        # Calculate new LSB to center the ink in the new advance width
        if glyf and glyph_name in glyf and glyf[glyph_name].numberOfContours != 0:
            glyph = glyf[glyph_name]
            glyph.recalcBounds(glyf)
            ink_width = glyph.xMax - glyph.xMin
            new_lsb = (new_width - ink_width) // 2
        else:
            # Composite or empty glyph — shift LSB proportionally
            new_lsb = old_lsb + (new_width - old_width) // 2

        hmtx.metrics[glyph_name] = (new_width, new_lsb)
        changed.append((glyph_name, old_width, new_width))

    return changed


def remove_hvar(font: TTFont) -> bool:
    """Remove HVAR table so gvar phantom points handle width interpolation."""
    if "HVAR" in font:
        del font["HVAR"]
        return True
    return False


def update_metadata(font: TTFont):
    """Recalculate OS/2 average width and fix monospace flags if needed."""
    if "OS/2" in font:
        font["OS/2"].recalcAvgCharWidth(font)


def build(config_path: str):
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = load_config(config_path)

    input_dir = os.path.join(project_dir, "input")
    output_dir = os.path.join(project_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    fonts = sorted(f for f in os.listdir(input_dir) if f.lower().endswith(".ttf"))
    if not fonts:
        print(f"No .ttf files in {input_dir}/")
        sys.exit(1)

    modifications = {k: v for k, v in cfg["modifications"].items() if not k.startswith("_")}
    if not modifications:
        print("No modifications defined in config.json")
        sys.exit(1)

    family = cfg["family_name"]
    allowed = cfg["allowed_widths"]

    print(f"Building '{family}'")
    print(f"Allowed widths: {allowed}")
    print(f"Modifications: {len(modifications)} glyphs")
    print()

    for filename in fonts:
        input_path = os.path.join(input_dir, filename)
        # Rename file: replace "iAWriter" with family name (no spaces)
        out_name = filename.replace("iAWriterQuattro", family.replace(" ", ""))
        out_name = out_name.replace("iA Writer Quattro", family.replace(" ", ""))
        # Fallback: if filename didn't match, just prefix
        if out_name == filename:
            out_name = family.replace(" ", "") + "-" + filename
        output_path = os.path.join(output_dir, out_name)

        print(f"Processing {filename} -> {out_name}")
        font = TTFont(input_path)

        # Validate allowed widths against what's actually in the font
        actual_widths = get_allowed_widths_from_font(font)
        config_allowed = set(allowed)
        # Width 0 is used for .notdef/NULL/CR — always allowed
        non_zero_actual = actual_widths - {0}
        if not config_allowed.issuperset(non_zero_actual):
            missing = non_zero_actual - config_allowed
            print(f"  WARNING: Font has widths {sorted(missing)} not in allowed_widths.")
            print(f"  Actual non-zero widths: {sorted(non_zero_actual)}")
            print(f"  Update allowed_widths in config.json to match.")

        # Apply width changes
        changed = apply_modifications(font, modifications, allowed)
        for name, old_w, new_w in changed:
            print(f"  {name}: {old_w} -> {new_w}")

        # Remove HVAR to avoid stale variation deltas
        if remove_hvar(font):
            print(f"  Removed HVAR table")

        # Update metadata
        update_metadata(font)

        # Rename font family
        rename_font(font, family)
        print(f"  Renamed to '{family}'")

        font.save(output_path)
        print(f"  Saved {output_path}\n")

    # Verify
    print("="*50)
    print("VERIFICATION")
    print("="*50)
    for filename in os.listdir(output_dir):
        if not filename.lower().endswith(".ttf"):
            continue
        path = os.path.join(output_dir, filename)
        font = TTFont(path)
        hmtx = font["hmtx"]
        print(f"\n{filename}:")
        for glyph_name in modifications:
            if glyph_name.startswith("_"):
                continue
            if glyph_name in hmtx.metrics:
                w, lsb = hmtx.metrics[glyph_name]
                print(f"  {glyph_name:24s}  width={w:4d}  lsb={lsb:4d}")
        # Print family name from name table
        name_table = font["name"]
        for record in name_table.names:
            if record.nameID == 1:
                print(f"  Font family name: {record.toUnicode()}")
                break
        font.close()

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Prepbook Quattro fonts")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    default_config = os.path.join(project_dir, "config.json")
    parser.add_argument("--config", default=default_config, help="Path to config.json")
    args = parser.parse_args()
    build(args.config)
