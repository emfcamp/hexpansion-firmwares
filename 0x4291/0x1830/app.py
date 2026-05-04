import app
import neopixel
import asyncio
from patterns.rainbow import RainbowPattern
from machine import Pin

_LED_DATA = None
_LAT_BASE = 49.5
_LAT_STEP = 0.05
_LON_BASE = -11.5
_LON_STEP = 0.07
_RAD_STEP = 0.05

class UKMap(app.App):
	def __init__(self, config=None):
		self.config = config
		global _LED_DATA
		_LED_DATA = open(f"/hexpansion_{config.port}/led.bin", "rb").read()

		config.pin[3].init(drive=Pin.DRIVE_3)
		self.leds = neopixel.NeoPixel(config.pin[3], 78)
		self.brightness = 0.1
		self.running = True
		self.pattern = RainbowPattern()

		config.pin[1].init(pull=Pin.PULL_UP)
		config.pin[1].irq(self.dimmer)

		config.pin[0].init(pull=Pin.PULL_UP)
		config.pin[0].irq(self.brighter)

	def dimmer(self, pin):
		self.brightness -= 0.05
		if self.brightness <= 0:
			self.brightness = 0

	def brighter(self, pin):
		self.brightness += 0.05
		if self.brightness >= 0.2:
			self.brightness = 0.2

	def update(self, delta=None):
		self.minimise()

	async def background_task(self):
		while True:
			if self.running:
				frame = self.pattern.next()
				for i, val in enumerate(frame*7):
					if i >= 78:
						break
					self.leds[i] = tuple(int(c * self.brightness) for c in val)
				self.leds.write()
				await asyncio.sleep(1/self.pattern.fps)
			else:
				await asyncio.sleep(1)

	def get_led_from_lat_lon(self, lat, lon):
		data = _LED_DATA
		best_i = -1
		best_d2 = 1e30
		best_r = 0.0
		n = len(data) // 3
		for i in range(n):
			b = i * 3
			led_lat = _LAT_BASE + data[b]     * _LAT_STEP
			led_lon = _LON_BASE + data[b + 1] * _LON_STEP
			dlat = led_lat - lat
			dlon = led_lon - lon
			d2 = dlat * dlat + dlon * dlon
			if d2 < best_d2:
				best_d2 = d2
				best_i = i
				best_r = data[b + 2] * _RAD_STEP
		if best_d2 <= best_r * best_r:
			return best_i
		return None

__app_export__ = UKMap
