import app
import asyncio
from events.emote import EmotePositiveEvent, EmoteNegativeEvent
from events.input import Button, BUTTON_TYPES, ButtonDownEvent, ButtonUpEvent
from system.eventbus import eventbus
from system.hexpansion.config import *
from system.scheduler.events import RequestForegroundPushEvent
from system.notification.events import ShowNotificationEvent
from app_components import clear_background, Menu
from app_components.tokens import symbols
import settings

class RedButton(app.App):
    def __init__(self, config):
        self.hexpansion_config = config
        self.app = app
        self.menu_items = [
            "Up Button",
             "Down Button",
            "Left Button", 
            "Right Button", 
            "Confirm Button", 
            "Cancel Button", 
            "Positive Emote", 
            "Negative Emote", 
            "Soft Reset", 
            "Hard Reset", 
            "Power Off"
            ]
        self.button = config.pin[2]
        self.button.init(Pin.IN, Pin.PULL_UP)
        self.chosen_event = None
        self.show_menu=False
        self.last_value = 1
        self.needs_foregrounding = False
        try:
            self.chosen_event = settings.get("redbutton_event")
        except KeyError:
            self.show_menu = True
        if not self.button.value():
            self.show_menu = True
        if self.chosen_event is None:
            self.show_menu = True
        else:
            print(f"Red button now set to: {self.chosen_event}")
        self.menu = Menu(
                self,
                self.menu_items,
                select_handler=self.select_handler,
                back_handler=self.back_handler,
            )
        if self.show_menu:
            self.needs_foregrounding = True
        self.plugged_in = True

    def back_handler(self):
        self.show_menu = False
        self.minimise()

    def select_handler(self, item, idx):
        settings.set("redbutton_event", item)
        settings.save()
        self.chosen_event = item
        print(f"Red button now set to {item}")
        eventbus.emit(ShowNotificationEvent(message=f"Big Button {symbols["arrows"]["right"]} {item}"))
        self.show_menu = False
        self.minimise()
                
    def update(self, delta):
        if self.needs_foregrounding:
            print("FG Push")
            eventbus.emit(RequestForegroundPushEvent(self))
            self.needs_foregrounding = False
        if self.show_menu:
            self.menu.update(delta)

    def deinit(self):
        self.last_value = 0

    def draw(self,ctx):
        if not self.show_menu:
            self.minimise()
        else:
            clear_background(ctx)
            if self.show_menu:
                self.menu.draw(ctx)
    
    async def background_task(self):
        while True:
            if not self.show_menu:
                state = self.button.value()
                if (not state) and (self.last_value != state):
                    await self.handle_button_press()
                self.last_value = state
            await asyncio.sleep(0.05)

    async def handle_button_press(self):
        print(f"Red button performing {self.chosen_event}")
        if self.chosen_event == self.menu_items[0]:
            await eventbus.emit_async(ButtonDownEvent(button=BUTTON_TYPES["UP"]))
        elif self.chosen_event == self.menu_items[1]:
            await eventbus.emit_async(ButtonDownEvent(button=BUTTON_TYPES["DOWN"]))
        elif self.chosen_event == self.menu_items[2]:
            await eventbus.emit_async(ButtonDownEvent(button=BUTTON_TYPES["LEFT"]))
        elif self.chosen_event == self.menu_items[3]:
            await eventbus.emit_async(ButtonDownEvent(button=BUTTON_TYPES["RIGHT"]))
        elif self.chosen_event == self.menu_items[4]:
            await eventbus.emit_async(ButtonDownEvent(button=BUTTON_TYPES["CONFIRM"]))
        elif self.chosen_event == self.menu_items[5]:
            await eventbus.emit_async(ButtonDownEvent(button=BUTTON_TYPES["CANCEL"]))
        elif self.chosen_event == self.menu_items[6]:
            await eventbus.emit_async(EmotePositiveEvent())
        elif self.chosen_event == self.menu_items[7]:
            await eventbus.emit_async(EmoteNegativeEvent())
        elif self.chosen_event == self.menu_items[8]:
            # Soft reset
            import sys
            sys.exit()
        elif self.chosen_event == self.menu_items[9]:
            # Hard reset
            import machine
            machine.reset()
        elif self.chosen_event == self.menu_items[10]:
            import power
            power.Off()
    
__app_export__ = RedButton