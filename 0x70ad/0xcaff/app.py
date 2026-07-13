import app
import asyncio
import time
from .adafruit_drv2605 import *
from machine import I2C, Pin
from events.emote import EmotePositiveEvent, EmoteNegativeEvent
from system.eventbus import eventbus
from system.hexpansion.events import HexpansionRemovalEvent, HexpansionInsertionEvent
from system.hexpansion.config import *
from system.notification.events import ShowNotificationEvent

class JitterHandler(app.App):
    def __init__(self, config):
        self.hexpansion_config = config
        self.app = app
        self.effect_start_time = 0
        self.effect_duration = 0
        self.need_to_stop = False
        self.drv = DRV2605(self.hexpansion_config.i2c)
        self.drv.library  = LIBRARY_TS2200B # This kicks it up a notch and stops the effects feeling pathetic!
        self.enable_pin = self.hexpansion_config.pin[3]
        self.enable_pin.init(Pin.OUT)
        self.enable_pin.off()
        self.effect_types = {
            "click": 1,
            "double_click":10,
            "double_click_long": 37,
            "triple_click":12,
            "buzz": 47,
            "tick": 24,
            "ramp_up_medium": 85,
            "ramp_up_short": 93,
            "ramp_up_long": 82,
            "ramp_down_short":81,
            "ramp_down_medium":73,
            "ramp_down_long":70,
            "continuous": 118,
            "hum":119,
        }
        eventbus.on_async(dict, self.handle_dict_event, self.app)
        eventbus.on_async(EmotePositiveEvent, self.handle_positive_emote, self.app)
        eventbus.on_async(EmoteNegativeEvent, self.handle_negative_emote, self.app)
        eventbus.on_async(ShowNotificationEvent, self.handle_notification, self.app)
        
    def update(self, delta):
        self.minimise()

    def deinit(self): # Stop trying to respond to events if the hexpansion gets yoinked
        eventbus.remove(dict, self.handle_dict_event, self.app)
        eventbus.remove(EmotePositiveEvent, self.handle_positive_emote, self.app)
        eventbus.remove(EmoteNegativeEvent, self.handle_negative_emote, self.app)
        eventbus.remove(ShowNotificationEvent, self.handle_notification, self.app)


    async def background_task(self):
        while True:
            if self.drv:
                if (self.need_to_stop) and (time.ticks_ms() - self.effect_start_time > self.effect_duration):
                    self.drv.stop()
                    self.enable_pin.off()
                    self.need_to_stop = False
            
            await asyncio.sleep(0.05)

    async def handle_dict_event(self, event):
        if event["type"] == "haptic" and "haptic_type" in event:
            if self.drv:
                self.enable_pin.on()
                if event["effect"] in self.effect_types:
                    self.drv.sequence[0] = Effect(self.effect_types[event["haptic_type"]])
                    self.drv.play()
                    if event["haptic_type"] == "continuous" or event["haptic_type"] == "hum":
                        if "duration" in event:
                            self.effect_duration = event["duration"]
                        else:
                            self.effect_duration = 500 # default to 500ms
                            print("No duration given, defaulting to 0.5s")
                        self.need_to_stop = True
                        self.effect_start_time = time.ticks_ms()
                else:
                    print ("Error: Effect type given in event not in known effect types")


    async def handle_positive_emote(self, event):
        if self.drv:
            self.enable_pin.on()
            self.drv.sequence[0] = Effect(self.effect_types["ramp_up_long"])
            self.drv.play()

    async def handle_negative_emote(self, event):
        if self.drv:
            self.enable_pin.on()
            self.drv.sequence[0] = Effect(self.effect_types["ramp_down_long"])
            self.drv.play()

    async def handle_notification(self, event):
        if self.drv:
            self.enable_pin.on()
            self.drv.sequence[0] = Effect(self.effect_types["double_click"])
            self.drv.play()

__app_export__ = JitterHandler