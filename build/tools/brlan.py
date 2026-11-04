"""Emit and edit Benzin's brlan XML (`.xmlan`).

A brlan is a list of animated panes; each pane holds tags (RLPA pane transform, RLVC vertex/pane color, RLTS
texture SRT, RLTP texture swap), each tag holds entries that select one channel, each entry a list of keyframe
triplets. `<blend>` is the tangent (value units per frame, not a weight): 0 eases a segment like a smoothstep,
the segment's own slope makes it linear. `type2` is a channel name for RLPA but a number for RLVC (16 = pane
alpha), as Benzin writes it.
"""

import re

# RLPA channels, spelled the way Benzin writes them
X_TRANS, Y_TRANS = "X Translation", "Y Translation"
PANE_ALPHA = "16"                       # RLVC


def smooth(pts):
    """Keyframes with zero tangents -> each segment eases in and out."""
    return [(f, v, 0.0) for f, v in pts]


def entry(channel, keys, type1=0):
    L = [f'\t\t\t\t\t\t<entry type1="{type1}" type2="{channel}">']
    for f, v, t in keys:
        L += ['\t\t\t\t\t\t\t<triplet>',
              f'\t\t\t\t\t\t\t\t<frame>{f:.15f}</frame>',
              f'\t\t\t\t\t\t\t\t<value>{v:.15f}</value>',
              f'\t\t\t\t\t\t\t\t<blend>{t:.15f}</blend>',
              '\t\t\t\t\t\t\t</triplet>']
    L.append('\t\t\t\t\t\t</entry>')
    return L


def pane(name, tags, kind=0):
    """kind 0 = pane animation target, 1 = material animation target."""
    L = [f'\t\t\t\t<pane name="{name}" type="{kind}">']
    for tag, entries in tags:
        L.append(f'\t\t\t\t\t<tag type="{tag}">')
        for channel, keys in entries:
            L += entry(channel, keys)
        L.append('\t\t\t\t\t</tag>')
    L.append('\t\t\t\t</pane>')
    return "\n".join(L)


def document(framesize, panes, loop=True):
    """A complete .xmlan from scratch, for when rewriting beats patching."""
    return "\n".join([
        '<?xml version="1.0" encoding="utf-8"?>',
        '\t\t<xmlan version="2.1.12BETA" brlan_version="0008">',
        f'\t\t\t<pai1 framesize="{framesize}" flags="{"01" if loop else "00"}">',
        *panes,
        '\t\t\t</pai1>',
        '\t\t</xmlan>',
    ]) + "\n"


def drop_panes(xml, names):
    """Remove whole <pane> blocks so those panes fall back to their brlyt values.

    The donor's RLTP texture-swap tracks cycle a material through sprite frames that are now 4x4 stubs,
    so left in they would flicker the pane to nothing several times a second.
    """
    for n in names:
        xml, k = re.subn(rf'\n?\t*<pane name="{re.escape(n)}" type="\d">.*?</pane>',
                         "", xml, flags=re.S)
        if not k:
            raise KeyError(f"no <pane name={n!r}> in brlan")
    return xml
