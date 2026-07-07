import app
import neopixel
import asyncio

PATH = __file__.rsplit("/", 1)[0]

class Monster(app.App):
	CAPABILITIES = ['neopixels', 'grouped_neopixels', 'leds_running']

	LED_GROUPS = {
		"eyes": [0, 1],
	}

	def __init__(self, config=None):
		self.config = config
		
		self.inner_leds = neopixel.NeoPixel(config.pin[3], 2)	# grouped_neopixels capability
		self.alignment = 0
		self.setup_led_group('eyes')
		self.brightness = 0.1
		self.leds_running = True	# leds_running capability

	# grouped_neopixels capability
	def setup_led_group(self, led_group_name):
		self.leds = neopixel.MergedNeoPixel(self.inner_leds, self.LED_GROUPS[led_group_name])
	# End grouped_neopixels capability

	def update(self, delta=None):
		self.minimise()

	async def background_task(self):
		while True:
			if self.leds_running:
				self.leds[0] = (0, 255, 0)
				self.leds[1] = (0, 255, 0)
				self.leds.write()
				await asyncio.sleep(1)
			else:
				await asyncio.sleep(1)

__app_export__ = Monster
