"""Edit Benzin's brlyt XML (`.xmlyt`) with the smallest possible delta.

The layout is derived from Tantric's donor, never emitted from scratch: a hand-built minimal brlyt omitted the
`fnl1` and `grp1` sections, which the Menu dereferences unconditionally, and black-screened it. So every section,
pane and name is kept (names live in a fixed 16-byte field that spills into `userdata`, and brlans refer to them);
only geometry, visibility and materials change.
"""

import re

# Benzin writes self-closing <tag type="pas1" /> markers between panes. A naive
# `<tag ...>(.*?)</tag>` matches one of those and then swallows the whole next
# pane, so the attribute group must be forbidden from ending in '/'.
TAGBLOCK = r'<tag type="(\w+)"((?:[^>]*[^/>])?)>(.*?)</tag>'
PANE_KINDS = ("pan1", "pic1", "txt1", "wnd1")


def _set(body, tag, value):
    return re.sub(rf"<{tag}>[^<]*</{tag}>", f"<{tag}>{value}</{tag}>", body)


def _set_xy(body, group, x, y, z=None):
    if z is None:
        return re.sub(rf"(<{group}>\s*<x>)[^<]*(</x>\s*<y>)[^<]*(</y>)",
                      rf"\g<1>{x:.10f}\g<2>{y:.10f}\g<3>", body)
    return re.sub(rf"(<{group}>\s*<x>)[^<]*(</x>\s*<y>)[^<]*(</y>\s*<z>)[^<]*(</z>)",
                  rf"\g<1>{x:.10f}\g<2>{y:.10f}\g<3>{z:.10f}\g<4>", body)


def edit_panes(xml, spec, hide_others=True):
    """Apply `spec` -- {pane_name: {translate, size, scale, rotate, alpha}} -- and hide every other drawable pane.

    Panes in `spec` are forced visible at alpha ff unless the spec says otherwise: pane alpha multiplies down the
    tree, so the donor icon's `Logo00Pane` (alpha b4) would cap its child at 70% and flatten the fade.
    """
    seen = set()

    def fix(m):
        kind, attrs, body = m.groups()
        if kind not in PANE_KINDS:
            return m.group(0)
        nm = re.search(r'name="([^"]*)"', attrs)
        nm = nm.group(1) if nm else ""
        if nm == "RootPane":
            return m.group(0)
        if nm in spec:
            seen.add(nm)
            s = spec[nm]
            body = _set(body, "visible", "01")
            body = _set(body, "alpha", s.get("alpha", "ff"))
            if "translate" in s:
                body = _set_xy(body, "translate", *s["translate"], z=0.0)
            if "size" in s:
                w, h = s["size"]
                body = re.sub(r"(<size>\s*<width>)[^<]*(</width>\s*<height>)[^<]*(</height>)",
                              rf"\g<1>{w:f}\g<2>{h:f}\g<3>", body)
            body = _set_xy(body, "scale", *s.get("scale", (1.0, 1.0)))
            body = _set_xy(body, "rotate", *s.get("rotate", (0.0, 0.0)), z=0.0)
        elif hide_others:
            body = _set(body, "visible", "00")
        return f'<tag type="{kind}"{attrs}>{body}</tag>'

    out = re.sub(TAGBLOCK, fix, xml, flags=re.S)
    missing = set(spec) - seen
    if missing:
        raise KeyError(f"panes not found in donor layout: {sorted(missing)}")
    return out


def identity_materials(xml, names):
    """Reset a material's texture matrix to identity and stop it tiling.

    Donor materials such as `BackgroundMaterial` tile a half-width texture across a double-width pane (wrap_s
    GX_MIRROR on the banner, GX_REPEAT on the icon, plus XScale=2.0), so every wrap value and the scale must be
    reset, or a full-bleed image renders at half width and mirrored.
    """
    def mat(m):
        name, body = m.groups()
        if name in names:
            body = re.sub(r"<wrap_s>\w+</wrap_s>", "<wrap_s>GX_CLAMP</wrap_s>", body)
            body = re.sub(r"<wrap_t>\w+</wrap_t>", "<wrap_t>GX_CLAMP</wrap_t>", body)
            for f, v in (("XTrans", 0.0), ("YTrans", 0.0), ("Rotate", 0.0),
                         ("XScale", 1.0), ("YScale", 1.0)):
                body = re.sub(rf"<{f}>[^<]*</{f}>", f"<{f}>{v:.10f}</{f}>", body)
        return f'<entries name="{name}">{body}</entries>'

    out = re.sub(r'<entries name="([^"]+)">(.*?)</entries>', mat, xml, flags=re.S)
    for n in names:
        if f'<entries name="{n}">' not in out:
            raise KeyError(f"material {n!r} not in donor layout")
    return out
