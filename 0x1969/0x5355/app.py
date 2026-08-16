"""
Space Unicorn — Tildagon control app.

A tile-based controller for the EMF26 Space Unicorn hexpansion: an ATtiny85 I2C
slave (address 0x40) driving WS2812 NeoPixels. Each tile drives one part of the
firmware register map (pattern, palette, speed, primary colour, LED count,
pattern parameter, reset) live over I2C.

Discovery works two ways:
  * EEPROM-resident: launched with a HexpansionConfig, uses I2C(config.port).
  * Store app / breadboard: scans hexpansion ports 1-6 for a device at 0x40.

Targets Tildagon OS v2 (hexpansion app discovery / event bus).

License: MIT
"""
import app
import time

from machine import I2C
from events.input import Buttons, BUTTON_TYPES
from tildagonos import tildagonos
from system.eventbus import eventbus
from system.hexpansion.events import HexpansionMountedEvent, HexpansionUnmountedEvent
from system.patterndisplay.events import PatternDisable, PatternEnable
from system.scheduler.events import (
    RequestForegroundPushEvent,
    RequestForegroundPopEvent,
    RequestStopAppEvent,
)

# Forward-compatible: emfcamp/badge-2024-software PR #321 lets a hexpansion app
# add itself to the launcher. Not in OS v2.0.0-alpha.4, so degrade gracefully.
try:
    from system.hexpansion.events import HexpansionAppLauncherAddEvent
    HAS_LAUNCHER_ADD = True
except ImportError:
    HAS_LAUNCHER_ADD = False

# --- Space Unicorn I2C protocol (from EMF_space_unicorn/test_registers.py) -----

ADDR = 0x40

REG_CTRL     = 0x00
REG_GLB_G    = 0x01
REG_GLB_R    = 0x02
REG_GLB_B    = 0x03
REG_PATTERN  = 0x04
REG_SPEED    = 0x05
REG_N_LEDS   = 0x06
REG_SEC_G    = 0x07
REG_SEC_R    = 0x08
REG_SEC_B    = 0x09
REG_PARAM1   = 0x0A
REG_PAL_SEL  = 0x0B

CTRL_RST     = 0x01
CTRL_GLB     = 0x02
CTRL_PAT_EN  = 0x04

PAT_OFF = 0

PATTERNS = {
    0: "Off",        1: "Solid",     2: "Chase",
    3: "Blink",      4: "Alternate", 5: "Wipe",
    6: "Twinkle",    7: "Rainbow",   8: "Rainbow Mtx",
    9: "Retro Blink",
}
N_PATTERNS = len(PATTERNS)

PALETTES = {
    0: "User",   1: "Fire",    2: "Ocean",
    3: "Forest", 4: "Party",   5: "Mono White",
    6: "Rainbow", 7: "Heat",
}
N_PALETTES = len(PALETTES)

# Default user-defined colours (firmware's USER palette leaves the registers
# unchanged, so the app supplies these): white foreground, black background.
USER_PRIM = (255, 255, 255)
USER_SEC = (0, 0, 0)

# Output modes (UI concept layered over the CTRL register)
OUT_PATTERN = 0
OUT_SOLID   = 1
OUT_OFF     = 2
OUTPUT_NAMES = ("Pattern", "Solid", "Off")


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def draw_bar(ctx, frac):
    """Horizontal progress bar in the tile's lower band (fuller = more)."""
    w = 120
    x0 = -w / 2
    y = 38
    ctx.line_width = 6
    ctx.rgb(0.25, 0.27, 0.32)
    ctx.begin_path()
    ctx.move_to(x0, y).line_to(x0 + w, y).stroke()
    ctx.rgb(0.0, 0.8, 0.55)
    ctx.begin_path()
    ctx.move_to(x0, y).line_to(x0 + w * frac, y).stroke()


# --- Tiles --------------------------------------------------------------------

class Tile:
    """One option screen. Subclasses override value/up/down/confirm/hints."""

    title = "Tile"

    def __init__(self, a):
        self.a = a

    def value(self):
        return ""

    def value_colour(self):
        return (1, 1, 1)

    def up(self):
        pass

    def down(self):
        pass

    def confirm(self):
        pass

    def hint(self):
        return "▲▼ change"

    def on_enter(self):
        pass

    def on_leave(self):
        pass

    def draw_extra(self, ctx):
        """Optional graphics drawn in the band below the value (y ~ +22..+52)."""
        pass


class OutputTile(Tile):
    title = "Output"

    def value(self):
        return OUTPUT_NAMES[self.a.output]

    def up(self):
        self.a.output = (self.a.output - 1) % 3
        self.a.apply_output()

    def down(self):
        self.a.output = (self.a.output + 1) % 3
        self.a.apply_output()


class PatternTile(Tile):
    title = "Pattern"

    def value(self):
        return PATTERNS[self.a.pattern]

    def up(self):
        self.a.set_pattern((self.a.pattern - 1) % N_PATTERNS)

    def down(self):
        self.a.set_pattern((self.a.pattern + 1) % N_PATTERNS)


class PaletteTile(Tile):
    title = "Palette"

    def value(self):
        return PALETTES[self.a.palette]

    def up(self):
        self.a.set_palette((self.a.palette - 1) % N_PALETTES)

    def down(self):
        self.a.set_palette((self.a.palette + 1) % N_PALETTES)

    def draw_extra(self, ctx):
        self.a.draw_swatch(ctx, -34, 36, self.a.prim, "P")
        self.a.draw_swatch(ctx, 4, 36, self.a.sec, "S")


class ColourTile(Tile):
    """Edit the primary colour; preview it live on the badge ring."""

    title = "Colour"
    CH_NAMES = ("Red", "Green", "Blue")
    CH_COLOURS = ((1, 0.3, 0.3), (0.3, 1, 0.3), (0.4, 0.6, 1))

    def __init__(self, a):
        super().__init__(a)
        self.ch = 0

    def value(self):
        return "{} {}".format(self.CH_NAMES[self.ch], self.a.prim[self.ch])

    def value_colour(self):
        return self.CH_COLOURS[self.ch]

    def up(self):
        self._adjust(16)

    def down(self):
        self._adjust(-16)

    def _adjust(self, d):
        self.a.prim[self.ch] = clamp(self.a.prim[self.ch] + d, 0, 255)
        self.a.write_primary()
        self.a.ring_preview()

    def confirm(self):
        self.ch = (self.ch + 1) % 3

    def hint(self):
        return "OK channel • ▲▼ value"

    def on_enter(self):
        self.a.ring_take()

    def on_leave(self):
        self.a.ring_release()

    def draw_extra(self, ctx):
        self.a.draw_swatch(ctx, -18, 34, self.a.prim, None, w=36, h=20)


class NumberTile(Tile):
    def __init__(self, a, title, reg, attr, lo, hi, step, suffix=""):
        super().__init__(a)
        self.title = title
        self.reg = reg
        self.attr = attr
        self.lo = lo
        self.hi = hi
        self.step = step
        self.suffix = suffix

    def value(self):
        return "{}{}".format(getattr(self.a, self.attr), self.suffix)

    def up(self):
        self._set(self.step)

    def down(self):
        self._set(-self.step)

    def _set(self, d):
        v = clamp(getattr(self.a, self.attr) + d, self.lo, self.hi)
        setattr(self.a, self.attr, v)
        self.a.write_reg(self.reg, v)

    def draw_extra(self, ctx):
        frac = (getattr(self.a, self.attr) - self.lo) / (self.hi - self.lo)
        draw_bar(ctx, frac)


class SpeedTile(Tile):
    """Animation speed. The firmware's REG_SPEED is ticks-per-frame (1 = fast,
    255 = slow); the UI inverts it so a higher number / fuller bar = faster."""

    title = "Speed"
    STEP = 5

    def value(self):
        return str(256 - self.a.speed)   # 1..255, higher = faster

    def up(self):      # faster -> fewer ticks per frame
        self._set(self.a.speed - self.STEP)

    def down(self):    # slower -> more ticks per frame
        self._set(self.a.speed + self.STEP)

    def _set(self, v):
        v = clamp(v, 1, 255)
        self.a.speed = v
        self.a.write_reg(REG_SPEED, v)

    def draw_extra(self, ctx):
        draw_bar(ctx, (256 - self.a.speed) / 255.0)   # fuller = faster


class ParamTile(Tile):
    """Param 1 (REG_PARAM1) — meaning depends on the current pattern.

    Retro Blink: number of LEDs flipped per frame (1-8).
    Rainbow Mtx: bit 0 selects the grid wiring (row-major vs serpentine).
    Every other pattern ignores it, so the tile greys out.
    """

    PAT_RETRO = 9
    PAT_MATRIX = 8

    @property
    def title(self):
        if self.a.pattern == self.PAT_RETRO:
            return "Flips/Frame"
        if self.a.pattern == self.PAT_MATRIX:
            return "Wiring"
        return "Param 1"

    def _applicable(self):
        return self.a.pattern in (self.PAT_RETRO, self.PAT_MATRIX)

    def value(self):
        if self.a.pattern == self.PAT_RETRO:
            return str(self.a.param1)
        if self.a.pattern == self.PAT_MATRIX:
            return "Zigzag" if (self.a.param1 & 1) else "Row"
        return "n/a"

    def value_colour(self):
        return (1, 1, 1) if self._applicable() else (0.4, 0.42, 0.48)

    def _set(self, v):
        self.a.param1 = v
        self.a.write_reg(REG_PARAM1, v)

    def up(self):
        if self.a.pattern == self.PAT_RETRO:
            self._set(clamp(self.a.param1 + 1, 1, 8))
        elif self.a.pattern == self.PAT_MATRIX:
            self._set(1)   # serpentine / zigzag

    def down(self):
        if self.a.pattern == self.PAT_RETRO:
            self._set(clamp(self.a.param1 - 1, 1, 8))
        elif self.a.pattern == self.PAT_MATRIX:
            self._set(0)   # row-major

    def hint(self):
        if self.a.pattern == self.PAT_RETRO:
            return "▲▼ flips 1-8"
        if self.a.pattern == self.PAT_MATRIX:
            return "▲ zigzag  ▼ row"
        return "Retro Blink / Rainbow Mtx only"


class ResetTile(Tile):
    title = "Reset"

    def value(self):
        return "press OK"

    def value_colour(self):
        return (1.0, 0.55, 0.0)

    def confirm(self):
        self.a.reset_device()

    def hint(self):
        return "OK = factory reset"


# --- App ----------------------------------------------------------------------

class SpaceUnicornApp(app.App):

    def __init__(self, config=None):
        super().__init__()
        self.config = config
        self.button_states = Buttons(self)

        # Live mirror of the device registers (RGB order for the colour fields).
        self.ctrl = 0
        self.pattern = 1
        self.palette = 0
        self.speed = 10
        self.n_leds = 64
        self.param1 = 1
        self.prim = list(USER_PRIM)   # primary (foreground) colour, RGB — default white
        self.sec = list(USER_SEC)     # secondary (background) colour, RGB — default black
        self.output = OUT_PATTERN

        self.i2c = None
        self.port = None
        self.connected = False
        self._scan_timer = 0
        self._ring_owned = False

        # Launched as an EEPROM-resident app (with a hexpansion port) vs from /apps.
        cfg_port = getattr(config, "port", None) if config else None
        self._is_resident = cfg_port is not None
        # Resident apps start backgrounded and aren't in the launcher, so they
        # must foreground themselves to be seen
        # (see https://tildagon.badge.emfcamp.org/hexpansions/writing-hexpansion-apps/).
        self._want_fg = self._is_resident
        # If we can register a launcher entry (PR #321 firmware), F can just
        # minimise and be re-foregrounded from the menu; otherwise F fully stops
        # so the resident copy and any /apps copy never run at the same time.
        self._can_relaunch = HAS_LAUNCHER_ADD and self._is_resident

        # Tile carousel
        self.tiles = [
            OutputTile(self),
            PatternTile(self),
            PaletteTile(self),
            ColourTile(self),
            SpeedTile(self),
            NumberTile(self, "LEDs", REG_N_LEDS, "n_leds", 1, 64, 1),
            ParamTile(self),
            ResetTile(self),
        ]
        self.idx = 0

        self.find_device()

        eventbus.on_async(RequestForegroundPushEvent, self._resume, self)
        eventbus.on_async(RequestForegroundPopEvent, self._pause, self)
        eventbus.on_async(HexpansionMountedEvent, self._mounted, self)
        eventbus.on_async(HexpansionUnmountedEvent, self._unmounted, self)

        # On firmware that supports it, add a persistent launcher entry so the
        # app can be reopened from the menu after exit (no-op on alpha.4).
        if self._can_relaunch:
            eventbus.emit(HexpansionAppLauncherAddEvent(cfg_port, "Space Unicorn"))

    # --- I2C layer --------------------------------------------------------

    def find_device(self):
        """Locate the unicorn: prefer our launch port, else scan ports 1-6."""
        candidates = []
        cfg_port = getattr(self.config, "port", None) if self.config else None
        if cfg_port:
            candidates.append(cfg_port)
        candidates += [p for p in range(1, 7) if p != cfg_port]

        for port in candidates:
            try:
                i2c = I2C(port)
                if ADDR in i2c.scan():
                    self.i2c = i2c
                    self.port = port
                    self.connected = True
                    self.read_state()
                    return True
            except Exception:
                continue
        self.i2c = None
        self.connected = False
        return False

    def write_reg(self, reg, val):
        try:
            self.i2c.writeto_mem(ADDR, reg, bytes([val & 0xFF]))
            return True
        except Exception:
            self.connected = False
            return False

    def read_reg(self, reg, default=0):
        try:
            return self.i2c.readfrom_mem(ADDR, reg, 1)[0]
        except Exception:
            self.connected = False
            return default

    def read_state(self):
        """Seed the UI from the live device registers."""
        self.ctrl = self.read_reg(REG_CTRL)
        self.prim = [self.read_reg(REG_GLB_R), self.read_reg(REG_GLB_G), self.read_reg(REG_GLB_B)]
        self.pattern = self.read_reg(REG_PATTERN, 1)
        self.speed = self.read_reg(REG_SPEED, 10)
        self.n_leds = self.read_reg(REG_N_LEDS, 64)
        self.sec = [self.read_reg(REG_SEC_R), self.read_reg(REG_SEC_G), self.read_reg(REG_SEC_B)]
        self.param1 = self.read_reg(REG_PARAM1, 1)
        self.palette = self.read_reg(REG_PAL_SEL)

        if self.ctrl & CTRL_PAT_EN:
            self.output = OUT_OFF if self.pattern == PAT_OFF else OUT_PATTERN
        elif self.ctrl & CTRL_GLB:
            self.output = OUT_SOLID
        else:
            self.output = OUT_PATTERN

    def write_primary(self):
        # Registers are in WS2812 order G, R, B; self.prim is R, G, B.
        self.write_reg(REG_GLB_G, self.prim[1])
        self.write_reg(REG_GLB_R, self.prim[0])
        self.write_reg(REG_GLB_B, self.prim[2])

    def write_secondary(self):
        self.write_reg(REG_SEC_G, self.sec[1])
        self.write_reg(REG_SEC_R, self.sec[0])
        self.write_reg(REG_SEC_B, self.sec[2])

    def apply_output(self):
        if self.output == OUT_PATTERN:
            self.write_reg(REG_PATTERN, self.pattern)
            self.write_reg(REG_CTRL, CTRL_PAT_EN)
            self.ctrl = CTRL_PAT_EN
        elif self.output == OUT_SOLID:
            self.write_primary()
            self.write_reg(REG_CTRL, CTRL_GLB)
            self.ctrl = CTRL_GLB
        else:  # OUT_OFF
            self.write_reg(REG_PATTERN, PAT_OFF)
            self.write_reg(REG_CTRL, CTRL_PAT_EN)
            self.ctrl = CTRL_PAT_EN

    def set_pattern(self, pid):
        self.pattern = pid
        self.output = OUT_PATTERN
        self.write_reg(REG_PATTERN, pid)
        self.write_reg(REG_CTRL, CTRL_PAT_EN)
        self.ctrl = CTRL_PAT_EN

    def set_palette(self, pid):
        self.palette = pid
        if pid == 0:
            # USER palette: the firmware leaves the colour registers unchanged,
            # so apply our defaults (white foreground, black background).
            self.prim = list(USER_PRIM)
            self.sec = list(USER_SEC)
            self.write_primary()
            self.write_secondary()
            self.write_reg(REG_PAL_SEL, 0)
        else:
            self.write_reg(REG_PAL_SEL, pid)
            time.sleep_ms(10)   # let the firmware load the palette on the STOP
            # Re-read the colours the firmware loaded so the swatches update.
            self.prim = [self.read_reg(REG_GLB_R), self.read_reg(REG_GLB_G), self.read_reg(REG_GLB_B)]
            self.sec = [self.read_reg(REG_SEC_R), self.read_reg(REG_SEC_G), self.read_reg(REG_SEC_B)]
        if self._ring_owned:
            self.ring_preview()

    def reset_device(self):
        self.write_reg(REG_CTRL, CTRL_RST)
        time.sleep_ms(50)
        self.read_state()

    # --- Badge LED ring (colour preview only) -----------------------------

    def ring_take(self):
        if self._ring_owned:
            return
        self._ring_owned = True
        eventbus.emit(PatternDisable())
        self.ring_preview()

    def ring_preview(self):
        if not self._ring_owned:
            return
        col = (self.prim[0], self.prim[1], self.prim[2])
        try:
            for i in range(12):
                tildagonos.leds[i + 1] = col
            tildagonos.leds.write()
        except Exception:
            pass

    def ring_release(self):
        if not self._ring_owned:
            return
        self._ring_owned = False
        try:
            for i in range(12):
                tildagonos.leds[i + 1] = (0, 0, 0)
            tildagonos.leds.write()
        except Exception:
            pass
        eventbus.emit(PatternEnable())

    # --- lifecycle --------------------------------------------------------

    async def _resume(self, _: RequestForegroundPushEvent):
        if not self.connected:
            self.find_device()
        if self.connected and isinstance(self.tiles[self.idx], ColourTile):
            self.ring_take()

    async def _pause(self, _: RequestForegroundPopEvent):
        self.ring_release()

    def background_update(self, delta):
        # Runs even while backgrounded. Request the foreground once after launch
        # (and after a re-mount) so the UI actually appears for the user.
        if self._want_fg:
            self._want_fg = False
            eventbus.emit(RequestForegroundPushEvent(self))

    async def _mounted(self, _):
        if not self.connected:
            self.find_device()
        if self._is_resident:
            self._want_fg = True

    async def _unmounted(self, e):
        if self.connected and getattr(e, "port", None) == self.port:
            self.connected = False
            self.i2c = None
            self.ring_release()

    def _goto(self, new_idx):
        new_idx %= len(self.tiles)
        if new_idx == self.idx:
            return
        self.tiles[self.idx].on_leave()
        self.idx = new_idx
        self.tiles[self.idx].on_enter()

    # --- update -----------------------------------------------------------

    def update(self, delta):
        btn = self.button_states
        if btn.get(BUTTON_TYPES["CANCEL"]):
            btn.clear()
            self.ring_release()
            if self._can_relaunch:
                # A launcher entry exists; just background, reopen from the menu.
                self.minimise()
            else:
                # No way back to this instance; fully stop so a resident copy and
                # an /apps copy never run simultaneously.
                eventbus.emit(RequestStopAppEvent(self))
            return

        if not self.connected:
            self._scan_timer += delta
            if self._scan_timer > 1000:
                self._scan_timer = 0
                self.find_device()
            return

        if btn.get(BUTTON_TYPES["LEFT"]):
            btn.clear()
            self._goto(self.idx - 1)
        elif btn.get(BUTTON_TYPES["RIGHT"]):
            btn.clear()
            self._goto(self.idx + 1)
        elif btn.get(BUTTON_TYPES["UP"]):
            btn.clear()
            self.tiles[self.idx].up()
        elif btn.get(BUTTON_TYPES["DOWN"]):
            btn.clear()
            self.tiles[self.idx].down()
        elif btn.get(BUTTON_TYPES["CONFIRM"]):
            btn.clear()
            self.tiles[self.idx].confirm()

        # If a previous tile owned the ring but we've navigated away (e.g. via a
        # path that skipped on_leave), make sure it is only held on the Colour tile.
        if self._ring_owned and not isinstance(self.tiles[self.idx], ColourTile):
            self.ring_release()

    # --- draw -------------------------------------------------------------

    def draw(self, ctx):
        ctx.rgb(0.05, 0.06, 0.10).rectangle(-120, -120, 240, 240).fill()

        if not self.connected:
            self._draw_status(ctx, "Space Unicorn", "not found", (0.93, 0.14, 0.0))
            return

        tile = self.tiles[self.idx]

        ctx.save()
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE

        # Title
        ctx.font_size = 20
        ctx.rgb(0.6, 0.7, 0.9).move_to(0, -84).text(tile.title.upper())

        # Central value
        ctx.font_size = 30
        ctx.rgb(*tile.value_colour()).move_to(0, -8).text(tile.value())

        # Per-tile extra graphics (swatches / bars)
        tile.draw_extra(ctx)

        # Hint
        ctx.font_size = 13
        ctx.rgb(0.55, 0.58, 0.65).move_to(0, 74).text(tile.hint())

        ctx.restore()
        self._draw_dots(ctx)

    def _draw_status(self, ctx, title, subtitle, colour):
        ctx.save()
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        ctx.font_size = 26
        ctx.rgb(*colour).move_to(0, -12).text(title)
        ctx.font_size = 16
        ctx.rgb(0.85, 0.85, 0.85).move_to(0, 18).text(subtitle)
        ctx.restore()

    def draw_swatch(self, ctx, x, y, rgb, label, w=30, h=22):
        ctx.save()
        ctx.rgb(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
        ctx.rectangle(x, y, w, h).fill()
        ctx.line_width = 1
        ctx.rgb(0.7, 0.7, 0.75)
        ctx.rectangle(x, y, w, h).stroke()
        if label:
            ctx.text_align = ctx.CENTER
            ctx.text_baseline = ctx.MIDDLE
            ctx.font_size = 12
            ctx.rgb(0.8, 0.82, 0.88).move_to(x + w / 2, y + h + 9).text(label)
        ctx.restore()

    def _draw_dots(self, ctx):
        ctx.save()
        n = len(self.tiles)
        gap = 12
        x0 = -(n - 1) * gap / 2
        y = 100
        for i in range(n):
            ctx.begin_path()
            if i == self.idx:
                ctx.rgb(0.0, 0.8, 0.55)
                ctx.arc(x0 + i * gap, y, 3.5, 0, 6.2832, False)
            else:
                ctx.rgb(0.35, 0.38, 0.45)
                ctx.arc(x0 + i * gap, y, 2.5, 0, 6.2832, False)
            ctx.fill()
        ctx.restore()


__app_export__ = SpaceUnicornApp  # pylint: disable=invalid-name
