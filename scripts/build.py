#!/usr/bin/env python3
"""Build Prepbook Quattro from iA Writer Quattro variable fonts.

Reads config.json for glyph width modifications and family name,
applies changes to all .ttf files in input/, writes results to output/.

Usage:
    python scripts/build.py
    python scripts/build.py --config custom-config.json
"""
import sys, os, json, argparse
from array import array
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent, GlyphCoordinates
from fontTools.ttLib.tables.ttProgram import Program

# Composite glyph component flag bits
ARGS_ARE_XY_VALUES = 0x0002
ROUND_XY_TO_GRID   = 0x0004


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


def rebuild_fractions(font: TTFont, cfg: dict) -> list[str]:
    """Replace precomposed fraction glyphs with composites of numr+fraction+dnom.

    Writes new composite records into the glyf table. No splines are drawn —
    only existing component glyphs are referenced. Clears any gvar entries
    for rebuilt glyphs so variation inherits from component deltas.
    """
    fr = cfg.get("fraction_rebuild") or {}
    if not fr.get("enabled"):
        return []
    glyf = font["glyf"]
    hmtx = font["hmtx"]
    adv = fr["advance_width"]
    lay = fr.get("layout") or {}
    auto_layout = bool(lay.get("auto", True))
    changed = []

    # Force gvar to fully decompile BEFORE we touch any glyph shape.
    # gvar decompiles lazily against the current glyf; if we modify glyf
    # first, decompilation later asserts on point-count mismatch.
    gvar = font.get("gvar")
    if gvar is not None:
        # LazyDict decompiles per-key on access; force eager decompile of
        # every entry so later pops don't try to re-decompile against a
        # glyph shape we've already rewritten.
        for _k in list(gvar.variations.keys()):
            _ = gvar.variations[_k]

    # Optionally reshape the `fraction` glyph: iA Quattro's fraction is
    # two disconnected 4-pt parallelograms (an upper-right bar and a
    # lower-left bar, sharing one slope and stroke width). This deletes
    # the upper bar and stretches the lower one along its own slope to
    # span the full original yMin..yMax, producing a single continuous
    # slash with the font's native fraction-slash angle.
    if fr.get("reshape_fraction_slash"):
        if "fraction" not in glyf:
            raise ValueError("Font has no 'fraction' glyph to reshape")
        original = glyf["fraction"]
        if original.numberOfContours != 2:
            print(
                f"  WARNING: 'fraction' has {original.numberOfContours} contours "
                f"(expected 2); skipping reshape"
            )
        else:
            # Preserve the 8-point / 2-contour structure so the original
            # gvar deltas still apply (→ slash varies with weight). We
            # only *reposition* the 8 points: upper contour becomes the
            # upper half of a continuous slash, lower contour becomes
            # the lower half, meeting at mid-y with matching geometry.
            coords = original.coordinates
            ends = original.endPtsOfContours

            # Contour 1 (lower bar) defines the slope + stroke width.
            c1_start = ends[0] + 1
            c1 = [(coords[j][0], coords[j][1]) for j in range(c1_start, ends[1] + 1)]
            # Pt order (both contours in source): top-left, top-right,
            # bottom-right, bottom-left.
            top_l, top_r, bot_r, bot_l = c1
            dy = top_l[1] - bot_l[1]
            dx = top_l[0] - bot_l[0]
            slope = (dx / dy) if dy else 0.0
            stroke_w = top_r[0] - top_l[0]  # horizontal stroke thickness

            # Anchor the full slash to pass through the lower contour's
            # bottom-left (bot_l) at y=bot_l[1] with the same slope.
            x0, y0 = bot_l
            def edge_x(y):
                return x0 + slope * (y - y0)

            y_bot = original.yMin
            y_top = original.yMax
            y_mid = (y_bot + y_top) // 2

            def pt(y, right=False):
                x = edge_x(y) + (stroke_w if right else 0)
                return (int(round(x)), int(y))

            # Upper contour (pts 0..3): y=[y_mid, y_top]
            new_c0 = [pt(y_top, right=False), pt(y_top, right=True),
                      pt(y_mid, right=True),  pt(y_mid, right=False)]
            # Lower contour (pts 4..7): y=[y_bot, y_mid]
            new_c1 = [pt(y_mid, right=False), pt(y_mid, right=True),
                      pt(y_bot, right=True),  pt(y_bot, right=False)]

            pts = new_c0 + new_c1

            # Center the ink within the glyph's existing advance width.
            old_adv, _ = hmtx.metrics["fraction"]
            xs = [p[0] for p in pts]
            ink_center = (min(xs) + max(xs)) / 2
            shift = int(round(old_adv / 2 - ink_center))
            pts = [(x + shift, y) for (x, y) in pts]

            new_frac = Glyph()
            new_frac.numberOfContours = 2
            new_frac.endPtsOfContours = [3, 7]
            new_frac.coordinates = GlyphCoordinates(pts)
            new_frac.flags = array("B", [1] * 8)  # all on-curve
            new_frac.program = Program()
            new_frac.program.fromBytecode(b"")

            glyf["fraction"] = new_frac
            new_frac.recalcBounds(glyf)
            hmtx.metrics["fraction"] = (
                old_adv,
                new_frac.xMin if hasattr(new_frac, "xMin") else 0,
            )
            # IMPORTANT: do NOT pop gvar — keeping deltas at the same
            # point indices preserves weight-axis variation. But we
            # *do* need to weld the seam: pt2/pt5 and pt3/pt4 are
            # coincident in base position, and if their original
            # deltas differ they split apart at non-default axis
            # values. Average their deltas so they move in lockstep.
            if gvar is not None:
                tvs = gvar.variations.get("fraction", [])
                welded = 0
                for tv in tvs:
                    dlist = tv.coordinates
                    for a, b in ((2, 5), (3, 4)):
                        da, db = dlist[a], dlist[b]
                        if da is None or db is None:
                            continue
                        avg = (
                            int(round((da[0] + db[0]) / 2)),
                            int(round((da[1] + db[1]) / 2)),
                        )
                        dlist[a] = avg
                        dlist[b] = avg
                    welded += 1
                print(f"  welded fraction seam across {welded} gvar tuple(s)")
            print(
                f"  reshaped 'fraction' (8 pts, 2 contours preserved): "
                f"y=[{y_bot},{y_top}] slope={slope:.3f}"
            )

    for target_name, spec in fr["targets"].items():
        if target_name.startswith("_"):
            continue
        if target_name not in glyf:
            print(f"  WARNING: fraction target '{target_name}' not in font, skipping")
            continue

        num_glyph = f'{spec["num"]}.numr'
        den_glyph = f'{spec["den"]}.dnom'
        for g in (num_glyph, "fraction", den_glyph):
            if g not in glyf:
                raise ValueError(
                    f"Missing component glyph '{g}' required to rebuild '{target_name}'"
                )

        if auto_layout:
            # Auto-compute offsets from actual component ink bounds so the
            # composite is centered in `adv` and the slash lands at the
            # boundary between numerator and denominator ink.
            ng = glyf[num_glyph]; ng.recalcBounds(glyf)
            dg = glyf[den_glyph]; dg.recalcBounds(glyf)
            fg = glyf["fraction"]; fg.recalcBounds(glyf)
            n_w = ng.xMax - ng.xMin
            d_w = dg.xMax - dg.xMin
            gap = int(lay.get("gap", 0))
            total = n_w + gap + d_w
            left_pad = (adv - total) // 2
            num_x_off = left_pad - ng.xMin
            den_x_off = (adv - left_pad - d_w) - dg.xMin
            # Center fraction slash at the boundary where numerator ink
            # ends and denominator ink begins.
            boundary = left_pad + n_w + gap // 2
            frac_x_off = boundary - (fg.xMin + fg.xMax) // 2
        else:
            num_x_off = int(lay.get("numerator_x", 0))
            frac_x_off = int(lay.get("fraction_x", 150))
            den_x_off = int(lay.get("denominator_x", 300))

        components = []
        for gname, x_off in (
            (num_glyph, num_x_off),
            ("fraction", frac_x_off),
            (den_glyph, den_x_off),
        ):
            c = GlyphComponent()
            c.glyphName = gname
            c.x, c.y = int(x_off), 0
            c.flags = ARGS_ARE_XY_VALUES | ROUND_XY_TO_GRID
            components.append(c)

        new_glyph = Glyph()
        new_glyph.numberOfContours = -1  # composite marker
        new_glyph.components = components
        glyf[target_name] = new_glyph

        # Recalculate bounds from components and set hmtx advance
        new_glyph.recalcBounds(glyf)
        new_lsb = new_glyph.xMin if hasattr(new_glyph, "xMin") else 0
        hmtx.metrics[target_name] = (adv, new_lsb)
        changed.append(target_name)

        # Clear any existing gvar entries — composite inherits variation
        # from the referenced numr/fraction/dnom components.
        if "gvar" in font:
            font["gvar"].variations.pop(target_name, None)

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

        # Rebuild precomposed fractions as composite glyphs
        rebuilt = rebuild_fractions(font, cfg)
        for name in rebuilt:
            print(f"  rebuilt fraction: {name}")

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
