# GodModeWii, Wii forwarder channel

Builds `GodModeWii - GMWA [cmyksoda].wad` and `GodModeWii - GMWA [cmyksoda] (vWii).wad`, Wii channels that
boot `sd:/apps/GodModeWii/boot.dol`. The title, title ID, app path and the tunnel's geometry and timing live in
`build/tools/config.py`; the icon's timeline and the size limits are at the top of `icon.py` and `banner.py`.

```
./build/build.sh
```

Builds the forwarder, then the sound, banner, icon and both WADs, runs the full verification pass, and
renders `preview/`. Needs devkitPro's devkitPPC with libogc, libfat and `elf2dol` (with `DEVKITPRO` and
`DEVKITPPC` set, as the Makefile reads both), `make`, `wine` (for Benzin), and Python 3; `build.sh` makes
its own venv with Pillow, pycryptodome and numpy on the first run.

> **`build/build.sh` will not run as-is from a fresh clone.** Four third-party inputs are deliberately not
> redistributed here, because a fakesigned Wii channel carries Nintendo's certificate chain and a ticket, and
> Benzin's redistribution terms are unchecked. All of them have fixed homes, so nothing needs repointing; create
> the directories and drop the files in:
>
> - `donor/FCE Ultra GX - FCEU [Tantric].wad`, the banner and icon donor, from the
>   [FCE Ultra GX](https://github.com/dborth/fceugx) channel installer.
> - `donor/USBLoaderGX_forwarder[UNEO].wad`, the ticket and TMD donor, from
>   [USB Loader GX](https://github.com/wiidev/usbloadergx) (`updates` branch).
> - `donor/vwii-nand-loader.app`, FIX94's vWii NAND loader r2, from `binary/vWii_NAND_Loader_svn_r2.zip` at commit
>   `2eed1fa0` of [tiny-vwii-nand-loader](https://github.com/FIX94/tiny-vwii-nand-loader). SHA-256
>   `69e4d631bee303c549aa813117fee623aa576f0d2693a4ee7c7679bf57993392`; `verify.py` checks it.
> - `build/tools/benzin/BENZIN.EXE` and its `CYGWIN1.DLL`, which do the `brlyt`/`brlan` XML round-trips. A Windows
>   binary; runs under plain `wine`.
>
> Everything else needed is in this repository.

## What goes on the SD card

```
sd:/apps/GodModeWii/boot.dol    <- GodModeWii itself, from its own release .zip
sd:/apps/GodModeWii/meta.xml
sd:/apps/GodModeWii/icon.png
```

The channel only needs `boot.dol` (or `boot.elf`) in that folder, on SD or USB.

## Channel properties

```
Title ID      00010001474D5741  ("GMWA")
Boot IOS      58
Contents      2 on Wii (banner archive / forwarder)
              3 on vWii (banner archive / NAND loader / forwarder)
Name          GodModeWii, in all ten language slots
Looks for     sd:/apps/GodModeWii/boot.dol, then boot.elf; then the same two on usb:
```

## How it is put together

| part | source | result |
|---|---|---|
| banner | `build/tools/tunnel.py`, `build/tools/art.py`, the FCE Ultra GX banner | 168,192 B uncompressed |
| icon | `build/tools/tunnel.py`, `icon/hbc-icon.png`, the FCE Ultra GX icon | 73,632 B uncompressed |
| sound | `audio/kebab-loop.wav` | 295,048 B |
| forwarder | `forwarder/main.c`, `forwarder/stub.S` | 311,776 B |

Content 0 is the FCE Ultra GX banner archive with `meta/banner.bin`, `meta/icon.bin` and `meta/sound.bin`
replaced and the IMET header rewritten (sizes, names, MD5). The ticket, TMD and certificate chain come from
USB Loader GX's forwarder, because its TMD already asks for what a forwarder wants: IOS58, AHB access, and
content 1 as the boot content. The title ID is changed to `GMWA`, the title key re-encrypted for it, the
contents re-hashed into the TMD, and both TMD and ticket fakesigned (`build/tools/build_wad.py`).

## The banner: an ASCII tunnel drawn by the GPU

The tunnel is a port of ascii-magic-art's
[Texture Tunnel](https://github.com/kailashsr38/ascii-magic-art/blob/main/pieces/tunnel.js) (MIT): every cell
of a character grid works out its angle and depth in a checkered tunnel and picks one of seven shade characters
in one of two color ramps. `build/tools/tunnel.py` keeps that math and changes three things: the colors
(GodModeWii's navy and teal), the shape (an ellipse fitted to the wide banner), and the speeds, which are rounded
so that the frame at 8 seconds is exactly the frame at 0 and the animation loops without a seam. The characters
are ` .:=+#@` in libogc's 8×16 console font, the one GodModeWii draws with.

A banner is a layout, not a program, so the tunnel has to be stored as pictures, and a full-size flipbook is
far too big: one 832×456 frame costs about 190 KB even at 4 bits a pixel, against a 600,000-byte budget for the
whole banner. So each frame is stored as a **map of which character goes in each cell**, and the Wii's GPU draws
the characters.

- The grid is 104×22 cells of 8×16 layout units, covering the 832×352 the Menu's button panel leaves visible.
  Each frame is a 104×22 **I4** texture, one texel per cell, holding a state from 0 to 14 (blank, or one of
  seven shades on one of two tones). That's 1,248 bytes of texture a frame.
- One **glyph atlas** holds a pre-colored tile per state, in a row.
- The material is GX's tile mode, the layout version of `GX_SetTevIndTile`: an indirect stage samples the frame
  at the cell, the indirect matrix turns its value into an offset of value × tile width into the atlas, and the
  TEV stage's indirect wrap makes the regular texture coordinate repeat once per cell.
- **GX can't wrap smaller than 16 texels** (the wrap sizes are 16, 32, 64, 128 and 256), so atlas tiles are
  16×32 texels: each 8×16 glyph blown up twice. An earlier build left a one-texel black gutter around each
  tile against seams at cell edges; in Dolphin the gutter itself showed as vertical stripes wherever a cell's
  sampling phase landed on it, so the tiles are now solid.
- **A real Wii loses texture coordinates past 1,024 texels.** Dolphin doesn't, so the first hardware test drew
  only the left third of a tunnel that spanned 3,328 atlas texels. The tunnel is now two tiles of 52×22 cells
  (832×704 atlas texels each): copies of the tunnel picture and its material, each placed over its half of the
  banner, and each with a second texture matrix that windows its half of the frame.
- **Strokes have to be 2 pixels wide.** In 16:9 the Menu squeezes the 832-unit banner into 640 pixels, which
  drops one column in four. Earlier builds drew the shades as 1-pixel dither and turned to stripes there; the
  console font's strokes are 2 pixels wide and come through whole.
- **Every frame's TPL header says NEAREST.** The Menu takes a texture's filters from its own TPL header, not from
  the layout, and a filtered index map blends neighboring states into garbage.
- `banner_Start` and `banner_Loop` are the same flipbook: an `RLTP` track on texture map 1 of the tunnel
  material, 96 frames at 12 per second (a key every 5 Menu frames, 480 frames in all). Because the two are the
  same, the hand-off from Start to Loop can't jump.

The research behind this, with sources, is in the project notes rather than this repository; the parts the build
relies on are checked by `verify.py`. The material comes out of Benzin as 172 bytes with flags `0x0384A222`, and
`banner.py` compares them byte for byte against an independent encoder before using the layout.

**Three traps in Benzin's XML:** its `TevColorClamp` field is really the TEV output register, and
`TevColorRegisterID` is really the clamp flag (the same for alpha). Harmless while both are zero and one, as
here, but don't trust the labels. Benzin reads a texture map's whole wrap byte as the wrap mode, so it can't
carry filter bits; that's one more reason the filters live in the TPL headers. And a pane's `<flag>` is NW4R's
location-adjust bit: `BackgroundPicture` has it set, and in 16:9 the Menu multiplies the position of a pane
that has it by 832/608. That's harmless for a pane at the center, but it spread the tiles apart into black
bands, so the copies clear it.

The logo is GodModeWii's own splash lettering, drawn in libogc's 8×16 console font, with the letters closed up
into solid black shapes (a 12-pixel square closing) and a 7-pixel outline with cut corners around them
(`build/tools/art.py`). It is stored as **CI4** (cyan, black and transparent), as is the atlas.

| texture | format | size |
|---|---|---|
| 96 tunnel frames | I4, NEAREST | 104×22 each |
| glyph atlas | CI4, NEAREST | 256×32 |
| logo | CI4 | 481×79 |
| 31 donor textures | RGB565 stub | 4×4 each |

## The icon

The icon is drawn **176×96**, so a 16:9 Menu (which shows about 171 layout units across) sees no black bars;
everything that has to be read stays in the middle 128 that a 4:3 Menu shows.

FCE Ultra GX's icon has four pictures. They are reused in draw order, and one picture is added on top:

| picture | becomes | animated by |
|---|---|---|
| `BackgroundPicture` | hidden; its two copies `Tunnel00Picture` and `Tunnel01Picture` (added) draw the tunnel as 2 tiles of 44×24 cells of 2×4 units, with the same tile material | `RLTP`, 30 frames at 12 per second, repeating every 2.5 s |
| `Goomba00Picture` | the logo, GodModeWii's Homebrew Channel lettering at 2× on a black box | `RLPA` X translation, right to left over 4.5 s |
| `Mario00Picture` | the drive list, six rows in gray on black | `RLPA` Y steps (the list scrolls once the cursor passes row 4), `RLVC` alpha |
| `Logo00Picture` | the teal cursor bar, one CI4 texture per row with that drive in white | `RLTP` per row, `RLPA` Y steps, `RLVC` alpha |
| `HeaderPicture` (added) | the navy title bar with "GodModeWii" | `RLVC` alpha |
| `FooterPicture` (added) | a black strip under the fourth drive row | `RLVC` alpha |

`HeaderPicture` and `FooterPicture`, with their materials, are copies of `Logo00Picture` and `Logo00Material`
with new names, placed last in the pane tree so they draw on top. The icon's tunnel shades are whole lit rows
rather than characters, since 2×4 cells are too small for letters.

**The Menu shows less of the icon than its 128×96.** A Wii U showed only about rows 8 to 88, so the title bar is
24 units tall with its text at row 8, and four drive rows fill 24 to 88. A Wii shows a pixel or two more at the
bottom, which `FooterPicture` covers. Across, a 4:3 Menu shows only the middle 128 units, so the text column is
centered, and the drive list leaves out GodModeWii's `[SEEP] seeprom:/`, whose 16 characters fill all 128.

The loop is 600 Menu frames (10 s): the marquee runs for frames 0 to 270, the drive list fades in over 30
frames, the cursor moves down one row every 36 frames from SD to KEYS (never back up), holding 63 frames on SD
and on KEYS, and the list fades out over the last 30 frames, back to the tunnel. The tunnel's 2.5 s period
divides the 10 s loop, so it never jumps.

**The icon size cap bricks.** `icon.bin` must decompress to at most `0x19000` bytes; over it, the System Menu
crashes right after the Health and Safety screen. This icon is 73,632 bytes, 72% of the cap.

## Sound

`audio/kebab-loop.wav` is **kebab** by Jallabert, rendered at 32 kHz with libopenmpt: pattern 1 once as an intro,
then pattern 2, which the song itself plays twice in a row, so its end runs straight back into its start.
`audio/kebab-loop.json` holds the loop point.

`build/tools/modloop.py` renders it. The song always plays from its first order, with the order list rewritten
to play the loop span twice more, so speed, tempo and volumes are whatever the song set up. The loop body is cut
from the first repeat and snapped to the waveform, so notes still ringing over the seam come from the loop's own
end. One trap for the `.mod` songs that were tried before kebab (an `.xm`, which stores its pattern count): **a
MOD file has no pattern count**, so players take the highest entry in all 128 order slots, and rewriting the
order list without keeping that entry makes the player read the samples from the wrong place.

`build/tools/sound.py` encodes it as a mono DSP-ADPCM BNS (Z-GX's encoder) with the loop flag on, the loop start
at sample 258,048 (8.064 s, a whole 14-sample frame), and the predictor and history at the loop start written
into the header so the decoder resumes cleanly after the jump. Round-trip SNR is 35.9 dB.

## Forwarder

`forwarder/` is the forwarder from my Empty Slot Creator, pointed at `/apps/GodModeWii/boot.dol`:

1. Mount SD and look for the path stored after `FWDPATH=`; if it's not there, mount USB (retrying for up to
   5 seconds while a drive spins up) and look there. `boot.elf` is tried after `boot.dol` on each.
2. Read the file into MEM2 and work out where its sections go.
3. Copy a small position-independent stub to `0x93000000`, shut everything down and jump to it. The stub copies
   the sections into place, writes `argv` (the app's path, the way the Homebrew Channel does) and jumps to the
   entry point.

`stub.S` is the real-mode start a Wii channel needs at `0x80003400`; current libogc doesn't provide one, and
without it a channel DOL shows a black screen forever.

**The system call trap.** GodModeWii's `boot.dol` is compressed with FIX94's dolxz. Its unpacker flushes the
cache, which ends in a system call (`sc`), before it installs its own handler for one. The Homebrew Channel's
older libogc leaves a self-contained handler at `0x80000C00`; libogc 3 leaves a vector there that jumps into the
forwarder's code, which the app has already overwritten, so a channel froze on the splash forever. The boot stub
now copies the same 44-byte handler dolxz uses to `0x80000C00` before anything else. Dolphin booting the app
directly never showed this, since dolxz skips that flush when it gets no `argv`.

**The loading screen** is new. Before it looks for the app, the forwarder sets up the screen exactly as
GodModeWii's `ui_init()` does (`console_init` with a 16-pixel margin, the console's own metrics) and draws
GodModeWii's FIGlet logo in bold cyan at row `rows / 2 - 6`, column `(cols - 61) / 2`, the same cell
GodModeWii's `ui_splash()` uses. GodModeWii then sets up the same screen and draws its own splash in the same
place, so the logo stays put and only the status line is new, as tested on a Wii. The
framebuffer is carved from the top of MEM1, so copying the app in low can't overwrite it while it's on screen,
but it ends under `0x817C0000`, where dolxz puts its second-stage loader and the `argv` text.
If the app isn't found, the forwarder says so in the status line's place and returns to the Wii Menu after five
seconds.

## vWii build

A Wii starts a channel at `0x80003400` in real mode (the stub above); a Wii U's vWii jumps straight to the DOL's
entry point instead, which is where this forwarder froze the console when it was built for Empty Slot Creator. So the vWii WAD gets one more content:
content 1 becomes FIX94's vWii NAND loader (r2, the same file USB Loader GX's own vWii forwarder uses), and the
forwarder moves to content 2, where the loader finds it and boots it the way the Homebrew Channel would. The
loader doesn't run on a Wii or in Dolphin, which starts channels the Wii's way.

## Sizes

| part | bytes (decompressed) | limit |
|---|---|---|
| `icon.bin` | 73,632 | **102,400 hard cap** (72%) |
| `banner.bin` | 168,192 | 600,000 self-imposed share (28%) |
| `sound.bin` | 295,048 | |

Banner memory is shared by every installed channel, and too much of it slows the Wii Menu and then freezes it
while paging the channel grid. The 600,000-byte share is the one my Z-GX channel settled on, under the
592,160 bytes LSD Dream Emulator's banner shipped with.

## Changes made to the FCE Ultra GX components

This is the GPL modification record for the parts derived from FCE Ultra GX.

**Banner** (`banner.brlyt`, `banner_Start.brlan`, `banner_Loop.brlan`; final copies in `layout/`)

- `BackgroundPicture` hidden. `Tunnel00Picture` and `Tunnel01Picture` added as copies of it, with
  `Tunnel00Material` and `Tunnel01Material` as copies of `BackgroundMaterial` replaced by the tile-mode material
  described above. Each covers half of the 832×352 above the Menu's button panel, with its location-adjust flag
  cleared.
- `LogoPane` and `LogoPicture` moved and resized for the outlined logo; `LogoMaterial` set to identity texture
  coordinates and pointed at the new logo texture.
- Every other pane hidden. Its texture is replaced by a 4×4 stub that keeps its name.
- Texture names added to `txl1` for the atlas, the first tunnel frame and the logo.
- Both animations replaced: every donor track removed, and the tunnel flipbook added as the only track.

**Icon** (`icon.brlyt`, `icon.brlan`; final copies in `layout/`)

- The four pictures reused as listed under [The icon](#the-icon), resized and moved; their materials pointed at
  new textures, with identity texture coordinates.
- `HeaderPicture`, `HeaderMaterial`, `FooterPicture` and `FooterMaterial` added as copies of `Logo00Picture`
  and `Logo00Material`.
- `BackgroundPicture` hidden. `Tunnel00Picture` and `Tunnel01Picture` added as copies of it, with
  `Tunnel00Material` and `Tunnel01Material` as copies of `BackgroundMaterial` replaced by the tile-mode material.
- Every donor texture replaced by a 4×4 stub that keeps its name.
- The animation replaced by a new 600-frame loop.

The forwarder is not derived from FCE Ultra GX; it is my own (GPL version 3 or later).

## Previews

`preview/` holds captures of the real Wii Menu in Dolphin, the same way as my VBoy Color GX channel's: the
banner open in 4:3 (640×480) and 16:9 (836×456), and the icon as a GIF of one exact 10-second loop of its tile
on the channel grid, every sixth Menu frame. The capture tool isn't part of this repository.

`build/tools/preview.py` renders the reference stills from the same frames and keyframes the WAD carries:
`banner/banner.png`, `banner/logo.png`, `icon/icon.png` and `splash/splash.png`. The bottom of the banner still
is black because the banner draws nothing there; the Menu's button panel covers it.

## Verification

`build/tools/verify.py` reads both finished WADs back off disk and checks the title ID, both fakesignatures,
content sizes and SHA-1s against the TMD, IOS58 and the donor's access rights, that the vWii boot content is
FIX94's loader byte for byte, the forwarder's app path, the IMET MD5, sizes and names, the U8 trees, the icon cap
and banner budget, the tile-mode material bytes of every tunnel tile in both layouts, that no tile spans more
than 1,024 atlas texels or keeps the location-adjust flag, NEAREST filtering on the atlas and all 126 index
maps, and that the sound loops from a whole frame. Run it before installing anything.

#### AI Disclosure

The entirety of *this* `.md` file was generated using Claude Code.
