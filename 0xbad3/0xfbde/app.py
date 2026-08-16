import app
from machine import I2C
from app_components import clear_background
from system.eventbus import eventbus
from events.input import Buttons, BUTTON_TYPES, ButtonDownEvent
from system.scheduler.events import RequestForegroundPushEvent
import frontboards.utils
from system.hexpansion.util import (
    detect_eeprom_addr,
    read_hexpansion_header,
)
from system.notification.events import ShowNotificationEvent

class FrontboardDetectApp(app.App):
    def __init__(self, config):
        self.button_states = Buttons(self)
        self.app = app
        eventbus.on(ButtonDownEvent, self._handle_buttondown, self)
        self.foregrounded = False
        self.i2c = I2C(0)
        self.i2c_scan = []
        try:
            addr, addr_len = detect_eeprom_addr(self.i2c)
            self.header = read_hexpansion_header(self.i2c, addr, addr_len=addr_len)
        except:
            self.header = None
        self.inc = 0


    def update(self, delta):
        self.i2c_scan = self.i2c.scan()
        if not self.foregrounded:  # Bring the app to the foreground on first run
            eventbus.emit(RequestForegroundPushEvent(self))
            self.foregrounded = True
        self.inc += 1
        if self.inc == 2:
            try:
                i2c = I2C(0)
                old_header = i2c.readfrom_mem(87, 0, 32, addrsize=16)
                print("Resetting frontboard")
                print(f"Old header: {old_header}")
                i2c.writeto(87, bytes([0,0,0,0,0,0,0,0]))
                frontboards.utils.detected_frontboard = None
                frontboard = frontboards.utils.detect_frontboard()
                if frontboard is None:
                    raise ValueError("No FB")
                print(f"Found frontboard {frontboard:04x}")
                addr, addr_len = detect_eeprom_addr(self.i2c)
                self.header = read_hexpansion_header(self.i2c, addr, addr_len=addr_len)
                if self.header is None:
                    raise ValueError("No header")
                eventbus.emit(ShowNotificationEvent(message="Found " + self.header.friendly_name))
            except Exception as e:
                print(e)
                eventbus.emit(ShowNotificationEvent(message="Failed"))

    def draw(self, ctx):
        ctx.save()
        clear_background(ctx)
        ctx.font_size = 30.0
        if self.header is not None:
            friendly_name = self.header.friendly_name
        else:
            friendly_name = "Not detected"
        text = f"{friendly_name}"
        width = ctx.text_width(text)
        height = ctx.font_size
        ctx.rgb(0, 1, 0).move_to(0 - (width / 2), (height / 2)).text(text)

        ctx.font_size = 12.0
        text = " ".join(f"{b:02x}" for b in self.i2c_scan)
        width = ctx.text_width(text)
        height = ctx.font_size
        ctx.rgb(1, 1, 1).move_to(0 - (width / 2), (height / 2) + 50).text(text)

        ctx.restore()
        return None

    def _handle_buttondown(self, event: ButtonDownEvent):
        if (BUTTON_TYPES["CANCEL"] in event.button) or (
            BUTTON_TYPES["CONFIRM"] in event.button
        ):
            self._cleanup()
            self.minimise()

    def _cleanup(self):
        eventbus.remove(ButtonDownEvent, self._handle_buttondown, self)


__app_export__ = FrontboardDetectApp
