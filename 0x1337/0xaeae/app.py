from app import App
from neopixel import NeoPixel
from tildagonos import tildagonos
from system.scheduler import scheduler
from system.eventbus import eventbus
import asyncio
from machine import Pin
from events.input import Button, BUTTON_TYPES, ButtonDownEvent, ButtonUpEvent
import settings

class ArcadeEditionApp(App):
    buttons = {
        "A": Button("A", "ArcadeEdition", BUTTON_TYPES["UP"]),
        "B": Button("B", "ArcadeEdition", BUTTON_TYPES["RIGHT"]),
        "C": Button("C", "ArcadeEdition", BUTTON_TYPES["CONFIRM"]),
        "D": Button("D", "ArcadeEdition", BUTTON_TYPES["DOWN"]),
        "E": Button("E", "ArcadeEdition", BUTTON_TYPES["LEFT"]),
        "F": Button("F", "ArcadeEdition", BUTTON_TYPES["CANCEL"]),
    }

    def __init__(self, config):
        self._config = config

        self._n = NeoPixel(config.pin[0], 12)
        self._port = config.port
        self._fps = 5

        for a in scheduler.apps:
            if 'PatternDisplay' == a.__class__.__name__:
                self._fps = a._p.fps

        self.pin_a = self.init_pin(config.ls_pin[4])
        self.pin_b = self.init_pin(config.ls_pin[3])
        self.pin_c = self.init_pin(config.ls_pin[2])
        self.pin_d = self.init_pin(config.ls_pin[0])
        self.pin_e = self.init_pin(config.pin[2])
        self.pin_f = self.init_pin(config.pin[3])

        self._pin_values = {'A': 1,'B': 1,'C': 1,'D': 1,'E': 1,'F': 1}

    def init_pin(self, pin):
        pin.init(Pin.IN)
        pin.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self.handle_pin)
        return pin

    async def background_task(self):
        while True:
            _o = settings.get("ae_led_o", "102") # def: grb
            for led in range(0, 12):
                self._n[led] = (tildagonos.leds[led+1][int(_o[0])], tildagonos.leds[led+1][int(_o[1])], tildagonos.leds[led+1][int(_o[2])])
            self._n.write()
            await asyncio.sleep(1 / self._fps)

    def handle_pin(self, pin):
        pin_id = False
        if pin.__class__.__name__ == 'ePin':
            if str(pin) == str(self.pin_a):
                pin_id = 'A'
            if str(pin) == str(self.pin_b):
                pin_id = 'B'
            if str(pin) == str(self.pin_c):
                pin_id = 'C'
            if str(pin) == str(self.pin_d):
                pin_id = 'D'
        else:
            if pin == self.pin_e:
                pin_id = 'E'
            if pin == self.pin_f:
                pin_id = 'F'

        if pin_id:
            pin_value = pin.value()

            if pin_value != self._pin_values[pin_id]:
                if pin_value:
                    eventbus.emit(ButtonDownEvent(button=self.buttons[pin_id]))
                else:
                    eventbus.emit(ButtonUpEvent(button=self.buttons[pin_id]))
                self._pin_values[pin_id] = pin_value


__app_export__ = ArcadeEditionApp
