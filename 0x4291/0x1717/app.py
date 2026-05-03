import app
import asyncio
from neopixel import NeoPixel
from machine import Pin
from tildagonos import tildagonos


def average_proportion(a, b, ratio):
    r = (a[0] * ratio + b[0]) // (ratio + 1)
    g = (a[1] * ratio + b[1]) // (ratio + 1)
    b = (a[2] * ratio + b[2]) // (ratio + 1)
    return (r,g,b)

class InfraRed(app.App):
    def __init__(self, config=None):
        self.config = config
        self.ir = config.pin[0]
        self.ir.init(mode=Pin.IN, pull=Pin.PULL_UP)
        config.pin[2].init(Pin.OUT, drive=Pin.DRIVE_3)
        config.pin[2].value(1)
        config.pin[3].init(Pin.OUT, drive=Pin.DRIVE_0)
        self.leds = NeoPixel(config.pin[3],5)
        
    def update(self, delta=None):
        self.minimise()

    async def background_task(self):
        while 1:
            bracket = tildagonos.leds[(2*self.config.port)-1], tildagonos.leds[(2*self.config.port)]
            self.leds[0] = bracket[0]
            self.leds[1] = average_proportion(bracket[0], bracket[1], 3)
            self.leds[2] = average_proportion(bracket[0], bracket[1], 1)
            self.leds[3] = average_proportion(bracket[1], bracket[0], 3)
            self.leds[4] = bracket[1]
            self.leds.write()
            await asyncio.sleep(0.1)

__app_export__ = InfraRed
