"""Every knob for the GodModeWii forwarder channel."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build/out"
FORWARDER_DOL = ROOT / "forwarder/forwarder.dol"
# Only the TMD, ticket and certs are reused: IOS58 with AHB access, no NAND loader.
DONOR = ROOT / "donor/USBLoaderGX_forwarder[UNEO].wad"
# The vWii can't boot the forwarder directly; FIX94's NAND loader boots it from content 2 there.
VWII_LOADER = ROOT / "donor/vwii-nand-loader.app"
VWII_LOADER_SHA256 = "69e4d631bee303c549aa813117fee623aa576f0d2693a4ee7c7679bf57993392"

TITLE = "GodModeWii"
TITLE_ID = "GMWA"
BOOT_PATH = "/apps/GodModeWii/boot.dol"
USERNAME = "cmyksoda"
WAD_NAMES = {"wii": f"GodModeWii - {TITLE_ID} [{USERNAME}].wad",
             "vwii": f"GodModeWii - {TITLE_ID} [{USERNAME}] (vWii).wad"}

# Banner tunnel: half-size cells over the part of the banner the Menu's button panel leaves visible.
BANNER_W, BANNER_H = 832, 456
CELL = (8, 16)
TUNNEL_COLS, TUNNEL_ROWS = 104, 22
# The shades, dark to bright, in GodModeWii's console font. Its strokes are 2 pixels wide, which
# survives the Menu squeezing a 16:9 banner sideways.
TUNNEL_RAMP = " .:=+#@"
# Real hardware loses texture coordinates past 1,024 texels, and a cell is 16x32 atlas texels, so the
# tunnel is drawn as tiles of at most 64x32 cells.
TUNNEL_SPLIT = ((0, 52, 104), (0, 22))
TUNNEL_CENTER_ROW = 10.55
TUNNEL_SCALE = (47, 15)
TUNNEL_PERIOD = 8.0
TUNNEL_FPS = 12
# Icon: drawn 176 wide so a 16:9 Menu (about 171 shown) sees no bars; 4:3 shows the middle 128.
ICON_W, ICON_H = 176, 96
ICON_CELL = (2, 4)
ICON_SPLIT = ((0, 44, 88), (0, 24))
ICON_PERIOD = 2.5
ICON_LOOP = 10.0
