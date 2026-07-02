from app import App
from tildagonos import tildagonos
import asyncio
import random

class RabbitApp(App):
    def __init__(self, config):
        self._led_r = config.ls_pin[4]
        self._led_r.init(self._led_r.PWM)

        self._led_g = config.ls_pin[2]
        self._led_g.init(self._led_g.PWM)

        self._led_b = config.ls_pin[3]
        self._led_b.init(self._led_b.PWM)

    async def background_task(self):
        self._eye_open()

        while True:
            open_time = random.uniform(3.0, 12.0)
            closed_time = random.uniform(0.1, 0.6)

            await asyncio.sleep(open_time)
            self._eye_close()
            await asyncio.sleep(closed_time)
            self._eye_open()

    def _eye_open(self):
        self._led_r.duty(15)

    def _eye_close(self):
        self._led_r.duty(0)

__app_export__ = RabbitApp
