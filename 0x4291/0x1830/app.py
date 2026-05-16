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


VERTICAL = (
	(69, 73),
	(56, 61, 65, 74),
	(54, 57, 62, 66, 70, 75),
	(58, 63, 67, 71),
	(55, 59, 60, 64, 68, 72),
	(3, 5, 9, 12, 38, 52),
	(1, 4, 6, 10, 13, 15, 18, 25, 31, 39, 45, 53),
	(2, 7, 14, 16, 19, 26, 32, 40, 46),
	(8, 11, 17, 20, 22, 27, 33, 47),
	(0, 21, 23, 28, 34, 41, 48),
	(24, 29, 35, 42, 49),
	(30, 36, 43, 50),
	(37, 44, 51),
)

HORIZONTAL = (
	(0,),
	(1, 2),
	(3, 4),
	(5, 6, 7, 8),
	(9, 10, 11),
	(12, 13, 14),
	(15, 16, 17),
	(18, 19, 20, 21, 54, 55),
	(22, 23, 24, 56, 57, 58, 59, 60),
	(25, 26, 27, 28, 29, 30, 61, 62, 63, 64, 65, 66, 67, 68),
	(31, 32, 33, 34, 35, 36, 37, 69, 70, 71, 72),
	(38, 39, 40, 41, 42, 43, 44, 73, 74, 75),
	(45, 46, 47, 48, 49, 50, 51),
	(52, 53),
)

COASTAL = (
	(0, 1, 2, 3, 4, 5, 8, 9, 11, 12, 14, 15, 17, 18, 21, 22, 24, 25, 26, 30, 31, 37, 38, 39, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 60, 61, 64, 65, 68, 69, 72, 73, 74, 75),
	(6, 7, 10, 13, 16, 19, 20, 23, 27, 29, 32, 36, 40, 41, 42, 43, 57, 58, 59, 62, 63, 66, 67, 70, 71),
	(28, 33, 34, 35),
)

DIAGONAL_NW_SE = (
	(52, 73, 74),
	(69, 70, 75),
	(53, 61, 65, 66, 71),
	(38, 45, 56, 62, 67, 72),
	(31, 39, 46, 47, 57, 58, 63, 64, 68),
	(25, 32, 40, 48, 54, 59),
	(26, 33, 41, 42, 49, 55, 60),
	(27, 34, 43, 50, 51),
	(15, 18, 19, 22, 28, 29, 35, 44),
	(12, 13, 16, 20, 23, 24, 30, 36, 37),
	(5, 9, 10, 14, 17, 21),
	(3, 6, 11),
	(1, 4, 7, 8),
	(2,),
	(0,),
)

DIAGONAL_NE_SW = (
	(50, 51),
	(37, 44, 49),
	(36, 42, 43, 47, 48),
	(30, 35, 41, 45, 46, 53),
	(29, 33, 34, 39, 40, 52),
	(24, 28, 32, 38),
	(21, 23, 26, 27, 31),
	(20, 22, 25, 72),
	(17, 19, 68, 71, 75),
	(16, 18, 60, 64, 66, 67, 70, 73, 74),
	(11, 13, 14, 15, 55, 58, 59, 62, 63, 65, 69),
	(7, 8, 10, 12, 54, 57, 61),
	(6, 9, 56),
	(2, 3, 4, 5),
	(0, 1),
)

LINE = tuple((a, ) for a in range(76))

OPTIONS = [VERTICAL, HORIZONTAL, COASTAL, DIAGONAL_NW_SE, DIAGONAL_NE_SW, LINE]


class UKMap(app.App):
	def __init__(self, config=None):
		self.config = config
		global _LED_DATA
		_LED_DATA = open(f"/hexpansion_{config.port}/led.bin", "rb").read()

		config.pin[3].init(drive=Pin.DRIVE_3)
		self.inner_leds = neopixel.NeoPixel(config.pin[3], 76)
		self.alignment = 0
		self.setup_neopixels()
		self.brightness = 0.1
		self.running = True
		self.pattern = RainbowPattern(self.leds.n)

		config.pin[1].init(pull=Pin.PULL_UP)
		config.pin[1].irq(self.dimmer, Pin.IRQ_FALLING)

		config.pin[0].init(pull=Pin.PULL_UP)
		config.pin[0].irq(self.realign, Pin.IRQ_FALLING)

	def dimmer(self, pin=None):
		self.brightness -= 0.05
		if self.brightness <= 0:
			self.brightness = 0.25

	def realign(self, pin=None):
		self.alignment += 1
		if self.alignment >= len(OPTIONS):
			self.alignment = 0
		self.setup_neopixels()
		self.pattern = RainbowPattern(self.leds.n)

	def setup_neopixels(self):
		self.leds = neopixel.MergedNeoPixel(self.inner_leds, OPTIONS[self.alignment])

	def update(self, delta=None):
		self.minimise()

	async def background_task(self):
		while True:
			if self.running:
				frame = self.pattern.next()
				for i, val in enumerate(frame*7):
					if i >= self.leds.n:
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
