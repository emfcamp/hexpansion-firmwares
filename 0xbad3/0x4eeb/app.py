from app import App
from app_components import clear_background
from app_components.dialog import KEYBOARD_BUTTONS
from events.input import BUTTON_TYPES, Buttons, ButtonDownEvent, ButtonUpEvent
from system.eventbus import eventbus
from system.hexpansion.config import *


# Based on https://gitlab.com/why2025/team-badge/firmware/-/blob/main/badgevms/drivers/tca8418.c
KEYCODES = [
    "NOTHING",
    "ESCAPE",  # 0x1
    "SQUARE",  # 0x2
    "TRIANGLE",  # 0x3
    "CROSS",  # 0x4
    "CIRCLE",  # 0x5
    "CLOUD",  # 0x6
    "DIAMOND",  # 0x7
    "BACKSPACE",  # 0x8
    "0",  # 0x9
    "MINUS",  # 0xa
    "GRAVE",  # 0xb
    "1",  # 0xc
    "2",  # 0xd
    "3",  # 0xe
    "4",  # 0xf
    "5",  # 0x10
    "6",  # 0x11
    "7",  # 0x12
    "8",  # 0x13
    "9",  # 0x14
    "TAB",  # 0x15
    "Q",  # 0x16
    "W",  # 0x17
    "E",  # 0x18
    "R",  # 0x19
    "T",  # 0x1a
    "Y",  # 0x1b
    "U",  # 0x1c
    "I",  # 0x1d
    "O",  # 0x1e
    "FN",  # 0x1f
    "A",  # 0x20
    "S",  # 0x21
    "D",  # 0x22
    "F",  # 0x23
    "G",  # 0x24
    "H",  # 0x25
    "J",  # 0x26
    "K",  # 0x27
    "L",  # 0x28
    "LSHIFT",  # 0x29
    "Z",  # 0x2a
    "X",  # 0x2b
    "C",  # 0x2c
    "V",  # 0x2d
    "B",  # 0x2e
    "N",  # 0x2f
    "M",  # 0x30
    "COMMA",  # 0x31
    "PERIOD",  # 0x32
    "LEFT",  # 0x33
    "DOWN",  # 0x34
    "RIGHT",  # 0x35
    "SLASH",  # 0x36
    "UP",  # 0x37
    "RSHIFT",  # 0x38
    "SEMICOLON",  # 0x39
    "APOSTROPHE",  # 0x3a
    "ENTER",  # 0x3b
    "EQUALS",  # 0x3c
    "LCTRL",  # 0x3d
    "LGUI",  # 0x3e
    "ALT",  # 0x3f
    "BACKSLASH",  # 0x40
    "SPACE",  # 0x41
    "SPACE",  # 0x42
    "SPACE",  # 0x43
    "ALT",  # 0x44
    "P",  # 0x45
    "LEFTBRACKET",  # 0x46
    "UNKNOWN",  # 0x47
    "UNKNOWN",  # 0x48
    "UNKNOWN",  # 0x49
    "UNKNOWN",  # 0x4a
    "UNKNOWN",  # 0x4b
    "UNKNOWN",  # 0x4c
    "UNKNOWN",  # 0x4d
    "UNKNOWN",  # 0x4e
    "UNKNOWN",  # 0x4f
    "RIGHTBRACKET",  # 0x50
]

CUSTOM_KEY_MAP = {
    "LSHIFT": "SHIFT",
    "RSHIFT": "SHIFT",
    "MINUS": "-",
    "GRAVE": "`",
    "COMMA": ",",
    "PERIOD": ".",
    "SLASH": "/",
    "SEMICOLON": ";",
    "APOSTROPHE": "'",
    "EQUALS": "=",
    "BACKSLASH": "\\",
    "LEFTBRACKET": "[",
    "RIGHTBRACKET": "]",
}

#  for symbol in """!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~"""


class KeyboardApp(App):
    def __init__(self, config=None):
        self.button_states = Buttons(self)
        self.hexpansion_config = config
        if self.hexpansion_config:
            self.init_keyboard()

    def update(self, delta):
        if self.button_states.get(BUTTON_TYPES["CANCEL"]):
            self.button_states.clear()
            self.minimise()

    def init_keyboard(self):
        self.ADDR = 0x34
        self.i2c = self.hexpansion_config.i2c
        # Based on https://github.com/Hack-a-Day/2025-Communicator_Badge/blob/main/firmware/badge/hardware/keyboard.py
        self.i2c.writeto_mem(
            self.ADDR, 0x1D, b"\xff"
        )  # KP_GPIO1 all ROW7:0 to KP matrix
        self.i2c.writeto_mem(
            self.ADDR, 0x1E, b"\xff"
        )  # KP_GPIO2 all COL7:0 to KP matrix
        self.i2c.writeto_mem(
            self.ADDR, 0x1F, b"\x03"
        )  # KP_GPIO3 all COL9:8 to KP matrix
        self.i2c.writeto_mem(
            self.ADDR, 0x01, b"\x91"
        )  # CFG Set the KE_IEN, INT_CFG, and AI bits
        # Clear Interrupts
        self.i2c.writeto_mem(self.ADDR, 0x02, b"\x01")  # INT_STAT K_INT 1 to clear
        irq_pin = self.hexpansion_config.pin[2]
        irq_pin.init(irq_pin.IN, irq_pin.PULL_UP)
        irq_pin.irq(self.handle_keyboard_irq, irq_pin.IRQ_FALLING)
        self.led_pin = self.hexpansion_config.pin[0]
        self.led_pin.init(self.led_pin.OUT)

    def handle_keyboard_irq(self, _):
        num_events = self.i2c.readfrom_mem(self.ADDR, 0x03, 1)
        for _ in range(num_events[0]):
            e = self.i2c.readfrom_mem(self.ADDR, 0x04, 1)
            pressed = bool(e[0] & 0x80)
            key = e[0] & 0x7F
            if key > 0:
                keycode = KEYCODES[key]
                if keycode == "SQUARE":
                    self.led_pin.off()
                if keycode == "CIRCLE":
                    self.led_pin.on()
                keycode = CUSTOM_KEY_MAP.get(keycode) or keycode
                button = KEYBOARD_BUTTONS.get(keycode)
                if button:
                    if pressed:
                        eventbus.emit(ButtonDownEvent(button=button))
                    else:
                        eventbus.emit(ButtonUpEvent(button=button))
        # Clear interrupt
        self.i2c.writeto_mem(self.ADDR, 0x02, b"\x01")  # INT_STAT K_INT 1 to clear


__app_export__ = KeyboardApp
