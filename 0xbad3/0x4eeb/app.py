from app import App
from app_components.dialog import KEYBOARD_BUTTONS
from events.input import Buttons, ButtonDownEvent, ButtonUpEvent
from system.eventbus import eventbus
import neopixel
from tildagonos import tildagonos
from system.scheduler import scheduler
import asyncio

# Based on https://gitlab.com/why2025/team-badge/firmware/-/blob/main/badgevms/drivers/tca8418.c
KEYCODES = [ "NOTHING", "ESCAPE", "SQUARE", "TRIANGLE", "CROSS", "CIRCLE", "CLOUD", "DIAMOND", "BACKSPACE", "0", "-", "`", "1", "2", "3", "4", "5", "6", "7", "8", "9", "TAB", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "FN", "A", "S", "D", "F", "G", "H", "J", "K", "L", "SHIFT", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "LEFT", "DOWN", "RIGHT", "/", "UP", "SHIFT", ";", "'", "ENTER", "=", "LCTRL", "SOLDERPARTY", "ALT", "\\", "SPACE", "SPACE", "SPACE", "ALT", "P", "[", "NA", "NA", "NA", "NA", "NA", "NA", "NA", "NA", "NA", "]", ]  # fmt: skip

SHIFTED_KEY_MAP = {
    "1": "!",
    "2": "@",
    "3": "#",
    "4": "$",
    "5": "%",
    "6": "^",
    "7": "&",
    "8": "*",
    "9": "(",
    "0": ")",
    "-": "_",
    "`": "~",
    ",": "<",
    ".": ">",
    "/": "?",
    ";": ":",
    "'": '"',
    "=": "+",
    "\\": "|",
    "[": "{",
    "]": "}",
}


HORIZONTAL = (
    (1, 2),
    (3, 0),
    (4, ),
    (8, 5,),
    (7, 6),
)

VERTICAL = (
    (1, 0, 8, 7,),
    (2, 3, 4, 5, 6),
)

class KeyboardApp(App):

    CAP = ["@neopixels/", "@merged_neopixels/"]

    LED_GROUPS = {
        "vertical": VERTICAL,
        "horizontal": HORIZONTAL,
    }

    def __init__(self, config=None):
        self.button_states = Buttons(self)
        self.hexpansion_config = config
        if self.hexpansion_config:
            self.init_keyboard()
        self.fps = 5
        for a in scheduler.apps:
            if "PatternDisplay" == a.__class__.__name__:
                self.fps = a._p.fps

    def init_keyboard(self):
        self.shifted = False
        self.fned = False
        self.ADDR = 0x34
        self.i2c = self.hexpansion_config.i2c
        # Based on https://github.com/Hack-a-Day/2025-Communicator_Badge/blob/main/firmware/badge/hardware/keyboard.py
        self.i2c.writeto_mem( self.ADDR, 0x1D, b"\xff")  # KP_GPIO1 all ROW7:0 to KP matrix
        self.i2c.writeto_mem( self.ADDR, 0x1E, b"\xff")  # KP_GPIO2 all COL7:0 to KP matrix
        self.i2c.writeto_mem( self.ADDR, 0x1F, b"\x03")  # KP_GPIO3 all COL9:8 to KP matrix
        self.i2c.writeto_mem( self.ADDR, 0x01, b"\x91")  # CFG Set the KE_IEN, INT_CFG, and AI bits
        # Clear Interrupts
        self.i2c.writeto_mem(self.ADDR, 0x02, b"\x01")  # INT_STAT K_INT 1 to clear
        irq_pin = self.hexpansion_config.pin[2]
        irq_pin.init(irq_pin.IN, irq_pin.PULL_UP)
        irq_pin.irq(self.handle_keyboard_irq, irq_pin.IRQ_FALLING)
        self.inner_leds = neopixel.NeoPixel(self.hexpansion_config.pin[0], 9)
        self.setup_led_group('horizontal')
        self.led_owner = None
        self.set_leds_color(0, 0, 0)
        self.follow_pattern = True

    def setup_led_group(self, led_group_name):
        self.leds = neopixel.MergedNeoPixel(self.inner_leds, self.LED_GROUPS[led_group_name])

    def set_leds_color(self, r, g, b):
        self.follow_pattern = False
        if self.led_owner is None or self.led_owner is self:
            self.leds.fill((r, g, b))
            self.leds.write()

    def handle_keyboard_irq(self, _):
        num_events = self.i2c.readfrom_mem(self.ADDR, 0x03, 1)
        for _ in range(num_events[0]):
            e = self.i2c.readfrom_mem(self.ADDR, 0x04, 1)
            pressed = bool(e[0] & 0x80)
            key = e[0] & 0x7F
            if key > 0:
                self.handle_keyboard_key(key, pressed)
        # Clear interrupt
        self.i2c.writeto_mem(self.ADDR, 0x02, b"\x01")  # INT_STAT K_INT 1 to clear

    def handle_keyboard_key(self, key, pressed):
        keycode = KEYCODES[key]
        if self.fned and pressed:
            if keycode == "SQUARE":
                self.set_leds_color(255, 0, 0)
            elif keycode == "TRIANGLE":
                self.set_leds_color(255, 128, 0)
            elif keycode == "CROSS":
                self.set_leds_color(255, 255, 0)
            elif keycode == "CIRCLE":
                self.set_leds_color(0, 255, 0)
            elif keycode == "CLOUD":
                self.set_leds_color(0, 0, 255)
            elif keycode == "DIAMOND":
                self.set_leds_color(128, 0, 255)
            elif keycode == "ESCAPE":
                self.set_leds_color(0, 0, 0)
            elif keycode == "SOLDERPARTY":
                self.set_leds_color(0, 0, 0)
                self.follow_pattern = True
            elif keycode == "SPACE":
                if self.led_owner is None or self.led_owner is self:
                    self.follow_pattern = False
                    self.leds[0] = (255, 0, 0)
                    self.leds[1] = (255, 255, 0)
                    if self.leds.n > 2:
                        self.leds[2] = (0, 255, 0)
                        self.leds[3] = (128, 0, 255)
                        self.leds[4] = (0, 0, 255)
                    self.leds.write()
            elif keycode == "RIGHT":
                self.setup_led_group("horizontal")
            elif keycode == "DOWN":
                self.setup_led_group("vertical")

        if keycode == "SHIFT":
            self.shifted = pressed
        elif keycode == "FN":
            self.fned = pressed
        else:
            button_keycode = keycode
            if self.shifted:
                button_keycode = SHIFTED_KEY_MAP.get(button_keycode) or button_keycode
            button = KEYBOARD_BUTTONS.get(button_keycode)
            if button:
                if pressed:
                    if self.shifted and button_keycode == keycode:
                        shift_button = KEYBOARD_BUTTONS.get("SHIFT")
                        eventbus.emit(ButtonDownEvent(button=shift_button))
                        eventbus.emit(ButtonDownEvent(button=button))
                        eventbus.emit(ButtonUpEvent(button=shift_button))
                    else:
                        eventbus.emit(ButtonDownEvent(button=button))
                else:
                    eventbus.emit(ButtonUpEvent(button=button))

    async def background_task(self):
        while True:
            if self.follow_pattern and (self.led_owner is None or self.led_owner is self):
                lp = 2 * self.hexpansion_config.port
                rp = 2 * ((self.hexpansion_config.port - 1) % 6)
                left_led = tildagonos.leds[lp]
                left_mid_led = tildagonos.leds[lp - 1]
                right_mid_led = tildagonos.leds[rp]
                right_led = tildagonos.leds[rp - 1]
                self.leds[0] = left_led
                self.leds[1] = left_mid_led
                if self.leds.n > 2:
                    self.leds[2] = (0, 0, 0)
                    self.leds[3] = right_mid_led
                    self.leds[4] = right_led
                self.leds.write()
            await asyncio.sleep(1 / self.fps)


__app_export__ = KeyboardApp
