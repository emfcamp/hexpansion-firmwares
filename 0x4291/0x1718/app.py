import app
import asyncio
import time
from neopixel import NeoPixel
from machine import Pin
from tildagonos import tildagonos

import settings
from events.input import BUTTON_TYPES, ButtonDownEvent, ButtonUpEvent, Button
from events.custom import CustomEvent
from frontboards.common import FRONTBOARD_BUTTON_TYPES
from system.eventbus import eventbus
from system.hexpansion.events import HexpansionAppLauncherAddEvent
from system.scheduler.events import RequestForegroundPushEvent
from system.notification.events import ShowNotificationEvent
from app_components import clear_background
from app_components.layout import LinearLayout, DefinitionDisplay, ButtonDisplay

# The IR encoding standards decoded by the ir_rx modules, paired with the
# receiver class that implements each one.
from .ir_rx import IR_RX
from .nec import NEC_8, NEC_16, SAMSUNG
from .sony import SONY_12, SONY_15, SONY_20
from .philips import RC5_IR, RC6_M0
from .mce import MCE

ENCODINGS = [
    ("NEC 8-bit", NEC_8),
    ("NEC 16-bit", NEC_16),
    #("Sony SIRC 12-bit", SONY_12),
    #("Sony SIRC 15-bit", SONY_15),
    #("Sony SIRC 20-bit", SONY_20),
    #("Philips RC-5", RC5_IR),
    #("Philips RC-6 mode 0", RC6_M0),
    #("Microsoft MCE", MCE),
    #("Samsung", SAMSUNG),
]

# Persisted selection, keyed by standard name, and the event type emitted for
# each decoded IR frame.
SETTING_KEY = "ir_encoding"
EVENT_SETTING_KEY = "ir_send_events"
CONTROL_SETTING_KEY = "ir_control"
IR_EVENT_TYPE = "ir_rx"

# IR Control emulates the badge buttons from received IR frames. Each physical
# System/Frontboard button gets an IR button parented to it, so emitting an
# event for the IR button is treated as a press of the real button. Each is
# mapped to an arbitrary NEC 8-bit command code (its index below).
CONTROL_BUTTONS = [
    BUTTON_TYPES["UP"],
    BUTTON_TYPES["DOWN"],
    BUTTON_TYPES["LEFT"],
    BUTTON_TYPES["RIGHT"],
    BUTTON_TYPES["CONFIRM"],
    BUTTON_TYPES["CANCEL"],
    FRONTBOARD_BUTTON_TYPES["A"],
    FRONTBOARD_BUTTON_TYPES["B"],
    FRONTBOARD_BUTTON_TYPES["C"],
    FRONTBOARD_BUTTON_TYPES["D"],
    FRONTBOARD_BUTTON_TYPES["E"],
    FRONTBOARD_BUTTON_TYPES["F"],
]

CONTROL_CODES = {
    value: Button(parent.name, "IR", parent=parent)
    for value, parent in enumerate(CONTROL_BUTTONS)
}

# NEC repeats every ~108ms while a key is held; drop the button this long after
# the last frame with no repeat.
CONTROL_RELEASE_MS = 200


def encoding_index(name):
    for i, (label, _cls) in enumerate(ENCODINGS):
        if label == name:
            return i
    return 0


def average_proportion(a, b, ratio):
    r = (a[0] * ratio + b[0]) // (ratio + 1)
    g = (a[1] * ratio + b[1]) // (ratio + 1)
    b = (a[2] * ratio + b[2]) // (ratio + 1)
    return (r,g,b)

class InfraRed(app.App):
    CAP = ["@neopixels/"]

    def __init__(self, config=None):
        self.config = config
        self.ir = config.pin[0]
        self.ir.init(mode=Pin.IN, pull=Pin.PULL_UP)
        config.pin[2].init(Pin.OUT, drive=Pin.DRIVE_3)
        config.pin[2].value(1)
        config.pin[3].init(Pin.OUT, drive=Pin.DRIVE_0)
        self.leds = NeoPixel(config.pin[3],5)
        self.led_owner = None
        self.foregrounded = False

        # UI: a single definition showing the selected IR encoding standard,
        # with a button below it to cycle to the next standard. The selection is
        # restored from the system settings.
        self.encoding_index = encoding_index(settings.get(SETTING_KEY, ENCODINGS[0][0]))
        self.encoding_display = DefinitionDisplay("Encoding", ENCODINGS[self.encoding_index][0])
        # First run is when no encoding has ever been saved; used to show the UI
        # once so the encoding can be configured.
        self.initialised = settings.get(SETTING_KEY) is not None

        # Toggle state. show_notifications is in-memory only (resets to off on
        # each launch); send_events and ir_control are restored from settings.
        self.show_notifications = False
        self.send_events = settings.get(EVENT_SETTING_KEY, True)
        self.ir_control = settings.get(CONTROL_SETTING_KEY, False)

        # IR Control state: the emulated button currently held down, and the
        # tick deadline at which it is released once the NEC repeats stop.
        self._held_button = None
        self._release_deadline = None
        self.ir_control_button = ButtonDisplay(
            self._toggle_text("IR Control", self.ir_control),
            button_handler=self.toggle_ir_control,
        )

        self.layout = LinearLayout([
            self.encoding_display,
            ButtonDisplay("Next", button_handler=self.advance_encoding),
            self._toggle_button("Notifications", "show_notifications"),
            self._toggle_button("Send events", "send_events", EVENT_SETTING_KEY),
            self.ir_control_button,
        ])
        eventbus.on_async(ButtonDownEvent, self._button_handler, self)

        # Time of the last received signal, seeded with a negative number so the LED
        # decay was finished from launch
        self.last_signal = -1000000

        # Deadline until which the lit LEDs are flashed red after a decode error.
        self._error_until = None

        # Instantiate the saved receiver on the IR pin.
        self.receiver = None
        self._install_receiver()

    @property
    def encoding(self):
        # The receiver class for the currently selected standard.
        return ENCODINGS[self.encoding_index][1]

    @property
    def encoding_name(self):
        return ENCODINGS[self.encoding_index][0]

    def _install_receiver(self):
        # Tear down any existing receiver (it owns the pin IRQ and a timer)
        # before instantiating the one for the current encoding standard.
        if self.receiver is not None:
            self.receiver.close()
        self.receiver = self.encoding(self.ir, self._on_ir)
        self.receiver.error_function(self._on_ir_error)

    def _on_ir_error(self, code):
        # A frame failed to decode: flash the lit LEDs red for 100ms.
        self._error_until = time.ticks_add(time.ticks_ms(), 100)

    def _on_ir(self, value, addr, ctrl):
        # Called by the receiver's decode IRQ for each frame received.
        self.last_signal = time.ticks_ms()
        if self.send_events:
            eventbus.emit(CustomEvent(
                IR_EVENT_TYPE,
                {
                    "encoding": self.encoding_name,
                    "value": value,
                    "addr": addr,
                    "ctrl": ctrl,
                },
            ))
        # A negative value is a status code (e.g. an NEC repeat while a key is
        # held), not a button; skip it so notifications show real frames only.
        if self.show_notifications and value >= 0:
            eventbus.emit(ShowNotificationEvent(
                f"{self.encoding_name}: value {value}, addr {addr}"
            ))
        # IR Control only makes sense for the NEC 8-bit command codes.
        if self.ir_control and self.encoding is NEC_8:
            self._ir_control_frame(value)

    def _ir_control_frame(self, value):
        # A repeat frame keeps the held button down; refresh the release timer.
        if value == IR_RX.REPEAT:
            if self._held_button is not None:
                self._arm_release()
            return
        button = CONTROL_CODES.get(value)
        if button is None:
            return
        # Release any previous button before pressing the new one so every
        # down is paired with an up.
        if self._held_button is not None:
            eventbus.emit(ButtonUpEvent(self._held_button))
        self._held_button = button
        eventbus.emit(ButtonDownEvent(button))
        self._arm_release()

    def _arm_release(self):
        # Push the release deadline out; the background task polls for it.
        self._release_deadline = time.ticks_add(time.ticks_ms(), CONTROL_RELEASE_MS)

    def _release(self):
        button = self._held_button
        self._held_button = None
        self._release_deadline = None
        if button is not None:
            eventbus.emit(ButtonUpEvent(button))

    @staticmethod
    def _toggle_text(label, value):
        return "{}: {}".format(label, "On" if value else "Off")

    def _toggle_button(self, label, attr, setting_key=None):
        # Build a ButtonDisplay that flips the boolean attribute `attr` on press,
        # updating its own text. If `setting_key` is given the value is persisted.
        button = ButtonDisplay(self._toggle_text(label, getattr(self, attr)))

        async def handler(event=None):
            value = not getattr(self, attr)
            setattr(self, attr, value)
            button.text = self._toggle_text(label, value)
            if setting_key is not None:
                settings.set(setting_key, value)
                settings.save()
            return True

        button.button_handler = handler
        return button

    def select_encoding(self, name):
        # Switch to the named encoding standard (see ENCODINGS), persisting the
        # choice and re-instantiating the receiver. Unknown names fall back to
        # the first standard.
        self.encoding_index = encoding_index(name)
        self.encoding_display.value = self.encoding_name
        settings.set(SETTING_KEY, self.encoding_name)
        settings.save()
        self._install_receiver()
        # IR Control only works with NEC 8-bit, so disable it when leaving.
        if self.ir_control and self.encoding is not NEC_8:
            self._set_ir_control(False)

    async def advance_encoding(self, event=None):
        next_index = (self.encoding_index + 1) % len(ENCODINGS)
        self.select_encoding(ENCODINGS[next_index][0])
        return True

    def _set_ir_control(self, enabled):
        self.ir_control = enabled
        settings.set(CONTROL_SETTING_KEY, self.ir_control)
        settings.save()
        self.ir_control_button.text = self._toggle_text("IR Control", self.ir_control)
        if not self.ir_control:
            # Release any button still held from the last frame.
            self._release()

    async def toggle_ir_control(self, event=None):
        # IR Control only works with NEC 8-bit; refuse to enable it otherwise.
        if not self.ir_control and self.encoding is not NEC_8:
            eventbus.emit(ShowNotificationEvent(
                "IR Control needs NEC 8-bit encoding", port=self.config.port
            ))
            return True
        self._set_ir_control(not self.ir_control)
        return True

    async def _button_handler(self, event):
        if BUTTON_TYPES["CANCEL"] in event.button:
            self.minimise()
            return
        await self.layout.button_event(event)

    def draw(self, ctx):
        clear_background(ctx)
        self.layout.draw(ctx)

    def update(self, delta=None):
        if not self.foregrounded:
            # Add to the hexpansion homescreen launcher so the app can be opened
            # later. On first run, show the UI so the encoding can be set up;
            # otherwise it sits in the background until launched.
            eventbus.emit(HexpansionAppLauncherAddEvent(self.config.port, "InfraRed"))
            if not self.initialised:
                eventbus.emit(RequestForegroundPushEvent(self))
            self.foregrounded = True

    @staticmethod
    def _active_led_count(elapsed_ms):
        # Fade out an LED for each order of magnitude of seconds since the last
        # signal. LED 0 is always lit.
        if elapsed_ms < 1000:
            return 5
        if elapsed_ms < 10000:
            return 4
        if elapsed_ms < 100000:
            return 3
        if elapsed_ms < 1000000:
            return 2
        return 1

    async def background_task(self):
        while 1:
            # Release a held IR Control button once its deadline has passed.
            if self._release_deadline is not None and \
                    time.ticks_diff(time.ticks_ms(), self._release_deadline) >= 0:
                self._release()
            if self.led_owner is None:
                elapsed = time.ticks_diff(time.ticks_ms(), self.last_signal)
                count = self._active_led_count(elapsed)
                if self._error_until is not None and \
                        time.ticks_diff(time.ticks_ms(), self._error_until) < 0:
                    # Flash the currently-lit LEDs red after a decode error.
                    colours = ((50, 0, 0),) * 5
                else:
                    bracket = tildagonos.leds[(2*self.config.port)-1], tildagonos.leds[(2*self.config.port)]
                    colours = (
                        bracket[0],
                        average_proportion(bracket[0], bracket[1], 3),
                        average_proportion(bracket[0], bracket[1], 1),
                        average_proportion(bracket[1], bracket[0], 3),
                        bracket[1],
                    )
                for i in range(5):
                    self.leds[i] = colours[i] if i < count else (0, 0, 0)
                self.leds.write()
            await asyncio.sleep(0.1)

__app_export__ = InfraRed
