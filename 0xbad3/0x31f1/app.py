import app
import settings
import power
from app_components import clear_background
from system.eventbus import eventbus
from events.input import Buttons, BUTTON_TYPES, ButtonDownEvent
from system.scheduler.events import RequestForegroundPushEvent


class WifiResetApp(app.App):
    def __init__(self, config):
        self.button_states = Buttons(self)
        self.app = app
        eventbus.on(ButtonDownEvent, self._handle_buttondown, self)
        settings.set("wifi_ssid", "emf")
        settings.set("wifi_wpa2ent_username", "badge")
        settings.set("wifi_password", "badge")
        settings.save()
        self.foregrounded = False

    def update(self, delta):
        if not self.foregrounded:  # Bring the app to the foreground on first run
            eventbus.emit(RequestForegroundPushEvent(self))
            self.foregrounded = True

    def draw(self, ctx):
        ctx.save()
        clear_background(ctx)
        ctx.font_size = 30.0
        text = "Wifi Reset!!"
        width = ctx.text_width(text)
        height = ctx.font_size
        ctx.rgb(0, 1, 0).move_to(0 - (width / 2), (height / 2)).text(text)
        ctx.restore()
        return None

    def _handle_buttondown(self, event: ButtonDownEvent):
        if (BUTTON_TYPES["CANCEL"] in event.button) or (
            BUTTON_TYPES["CONFIRM"] in event.button
        ):
            self._cleanup()
            self.minimise()

    def _cleanup(self):
        eventbus.remove(ButtonDownEvent, self._handle_buttondown, self.app)


__app_export__ = WifiResetApp
