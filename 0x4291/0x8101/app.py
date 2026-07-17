import app
from system.eventbus import eventbus
from system.a11y.printer import PrintA11y
from system.a11y.events import ReplaceAccessibiltiyHandlerEvent

import time

I2C_ADDR = 0x40
_STATUS_QUERY = bytes([0xFD, 0x00, 0x01, 0x21])
i2c = None

class ScreenReaderApp(app.App):

	def __init__(self, config):
		global i2c
		super().__init__()
		self.config = config
		i2c = config.i2c

	def update(self, delta):
		eventbus.emit(ReplaceAccessibiltiyHandlerEvent(SpeechA11yHandler))
		self.minimise()

class SpeechSynthesis:
	
	def __init__(self, i2c, addr=I2C_ADDR):
		self._i2c = i2c
		self._addr = addr

	def begin(self):
		for _ in range(40):
			self._i2c.writeto(self._addr, bytes([0xAA]))
			time.sleep_ms(50)
			self._i2c.writeto(self._addr, _STATUS_QUERY)
			if self._read_ack() == 0x4F:
				break
		self.set_volume(1)

	def _read_ack(self):
		try:
			return self._i2c.readfrom(self._addr, 1)[0]
		except OSError:
			return 0

	def _send_synthesis(self, enc, data):
		length = len(data) + 2
		self._i2c.writeto(self._addr, bytes([0xFD, length >> 8, length & 0xFF, 0x01, enc]))
		for i in range(0, len(data), 28):
			self._i2c.writeto(self._addr, data[i:i + 28])

	def _send_cmd(self, cmd):
		self._i2c.writeto(self._addr, bytes([0xFD, 0x00, 0x01, cmd]))

	def _wait(self):
		deadline = time.ticks_add(time.ticks_ms(), 5000)
		while self._read_ack() != 0x41:
			if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
				break
		time.sleep_ms(100)
		deadline = time.ticks_add(time.ticks_ms(), 10000)
		while True:
			if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
				break
			self._i2c.writeto(self._addr, _STATUS_QUERY)
			if self._read_ack() == 0x4F:
				break
			time.sleep_ms(20)

	def _speak_english(self, text):
		data = bytes(b & 0x7F for b in text.encode('latin-1'))
		self._send_synthesis(0x04, data)
		self._wait()

	def speak(self, text):
		self._speak_english(text)

	def set_volume(self, vol):         self._speak_english(f'[v{min(vol, 9)}]')
	def set_speed(self, speed):        self._speak_english(f'[s{min(speed, 9)}]')
	def set_tone(self, tone):          self._speak_english(f'[t{min(tone, 9)}]')
	def reset(self):                   self._speak_english('[d]')
	def enable_rhythm(self, on=True):  self._speak_english('[z1]' if on else '[z0]')
	def enable_pinyin(self, on=True):  self._speak_english('[i1]' if on else '[i0]')

	def set_sound_type(self, t):
		self._speak_english({0: '[m3]', 1: '[m51]', 2: '[m52]', 3: '[m53]', 4: '[m54]', 5: '[m55]'}[t])

	def set_english_pron(self, alphabet=True):  self._speak_english('[h1]' if alphabet else '[h2]')
	def set_speech_style(self, smooth=False):   self._speak_english('[f1]' if smooth else '[f0]')
	def set_zero_pron(self, ou=False):          self._speak_english('[o1]' if ou else '[o0]')
	def set_one_pron(self, yi=False):           self._speak_english('[y1]' if yi else '[y0]')
	def set_name_pron(self, force=True):        self._speak_english('[r1]' if force else '[r0]')

	def set_digital_pron(self, mode):  # 0=telephone, 1=numeric, 2=auto
		self._speak_english(f'[n{[1, 2, 0][mode]}]')

	def set_language(self, lang):  # 0=chinese, 1=english, 2=auto
		self._speak_english(f'[g{[1, 2, 0][lang]}]')

	def stop(self):    self._send_cmd(0x02)
	def pause(self):   self._send_cmd(0x03)
	def resume(self):  self._send_cmd(0x04)
	def sleep(self):   self._send_cmd(0x88)
	def wakeup(self):  self._send_cmd(0xFF)

class SpeechA11yHandler(PrintA11y):

	def __init__(self):
		super().__init__()
		self.synth = SpeechSynthesis(i2c)
		self.synth.begin()

	async def finalise_frame(self):
		text = self.get_deduped_strings()
		if text:
			self.synth.speak(" ".join(text))

__app_export__ = ScreenReaderApp
