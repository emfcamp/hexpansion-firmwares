import asyncio
from app import App
from .aw9523 import *

# Index of the list is the LED number according to the pinmap (except zero indexed) https://github.com/DanNixon/hexpansions/blob/main/makerspace-badge/README.md
# First value is the LED driver number (0 or 1)
# Second value is the LED driver address for that LED
# This could probably be much nicer
_MS_PINMAP = [ 
    (0, 0x2B),
    (0, 0x2C),
    (0, 0x2D),
    (0, 0x2E),
    (0, 0x2F),
    (0, 0x2A),
    (0, 0x29),
    (0, 0x28),
    (0, 0x27),
    (0, 0x26),
    (0, 0x25),
    (0, 0x24),
    (0, 0x23),
    (0, 0x22),
    (0, 0x21),
    (0, 0x20),
    (1, 0x2B),
    (1, 0x2C),
    (1, 0x2A),
    (1, 0x29),
    (1, 0x28),
    (1, 0x27),
    (1, 0x26),
    (1, 0x25),
    (1, 0x24),
    (1, 0x20),
    (1, 0x21),
    (1, 0x22),
    (1, 0x23),
]

# Source - https://stackoverflow.com/a/1257463
def pairs(lst):
    for i in range(1, len(lst)):
        yield lst[i-1], lst[i]
    yield lst[-1], lst[0]

class MSHexpansionApp(App):
    def __init__(self, config=None):
        self.AW9523 = None # This will actually be a list of two AW9523 objects since there's 2 on the hexpansion
        self.hexpansion_config = config
        if self.hexpansion_config:
            self.reinit_hexpansion()
        self.idx = 0 # Used for the animation

    def all_leds_off(self):
        if self.AW9523:
            for pin in _MS_PINMAP:
                self.AW9523[pin[0]][pin[1]] = 0

    def reinit_hexpansion(self):
        if self.hexpansion_config:
            self.AW9523 = [
                AW9523(self.hexpansion_config.i2c, address=0x5A),
                AW9523(self.hexpansion_config.i2c, address=0x5B),
            ]
            self.all_leds_off()

    async def background_task(self):
        while True:
            if self.AW9523:
                try:
                    for p in pairs(_MS_PINMAP):
                        expander_number, address = p[0]
                        self.AW9523[expander_number][address] = 0

                        expander_number, address = p[1]
                        self.AW9523[expander_number][address] = 50 # Can be up to 255, but That's Too Bright

                        await asyncio.sleep(0.05)

                except AttributeError:
                    print("Hexpansion removed!")
                    await asyncio.sleep(0.5)

            else:
                self.reinit_hexpansion()

__app_export__ = MSHexpansionApp
