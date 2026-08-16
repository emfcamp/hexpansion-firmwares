import vfs
import app
import sys
from machine import SDCard
from system.hexpansion.config import HexpansionConfig
from system.eventbus import eventbus
from system.launcher.app import InstallNotificationEvent
from system.launcher.app import AppDirAddedNotificationEvent, AppDirRemovedNotificationEvent
from app_components import Menu, Notification, clear_background
from system.scheduler.events import RequestForegroundPushEvent

# default location to mount the main flash device
MOUNTPATH = "/sdcard"
APPDIR = "/sdcard_apps"

# menu item text for three options
main_menu_items = ["Mount", "Remove", "Format"]

class SDHexpApp(app.App):
    def __init__(self, config=None):
        # if this is run from the EEPROM then config will be a HexpansionConfig for whatever slot it's plugged into
        # if not then we assume it's plugged into slot 2 (right hand side) for testing the app
        if config == None:
            config = HexpansionConfig(2)
        self.config = config

        # Make a menu GUI widget with the mount, unmount and format options
        self.menu = Menu(self, main_menu_items, select_handler=self.select_handler, back_handler=self.back_handler)

        # create a handle for the notification
        self.notification = None

        # create a flag to request foreground exactly once
        self.foregrounded = False

        # set up the power control pin, setting this to low (off) disables the card
        # this can be used to reset the card if it got into a bad state
        self.config.ls_pin[0].init(self.config.ls_pin[0].OUT)
        self.config.ls_pin[0].on()

        # set up SD Card in SPI mode
        # Slot 3 uses SPI1 which isn't the one driving the screen so should be free
        self.sd = SDCard(slot=3, sck=config.pin[2], cs=config.pin[0], mosi=config.pin[1], miso=config.pin[3])

        self.mounted = False

        # run the app class init
        super().__init__()

    def deinit(self):
        if self.mounted:
            vfs.umount(MOUNTPATH)
            if MOUNTPATH in sys.path:
                del sys.path[sys.path.index(MOUNTPATH)]
            eventbus.emit(AppDirRemovedNotificationEvent(MOUNTPATH+APPDIR))
            self.mounted = False
        self.sd.deinit()

    def select_handler(self, item, item_idx):
        # menu handler we try catch this whole thing to keep the code small for embedding in the EEPROM
        try:
            if item == "Mount":
                # mounts the device at the default location
                vfs.mount(self.sd, MOUNTPATH)
                sys.path.append(MOUNTPATH)
                eventbus.emit(AppDirAddedNotificationEvent(MOUNTPATH+APPDIR))
                self.mounted = True
            elif item == "Remove":
                # unmounts (safely removes) the storage
                self.deinit()
            elif item == "Format":
                # Format the drive as FAT
                vfs.VfsFat.mkfs(self.sd)
            # if the try-catch hasn't jumped out yet then what we tried to do must have succeded
            self.notification = Notification(f"{item} succeded")
        except Exception as err:
            # let the user know something went wrong
            self.notification = Notification(f"{item} failed {err}")

    def back_handler(self):
        # no state is saved in the app just minimise when the user is done with their choices
        self.minimise()

    # ctx GUI stuff just taken from the examples
    def draw(self, ctx):
        clear_background(ctx)
        self.menu.draw(ctx)
        if self.notification:
            self.notification.draw(ctx)

    def update(self, delta):
        if not self.foregrounded: # Bring the app to the foreground on first run
            eventbus.emit(RequestForegroundPushEvent(self))
            self.foregrounded = True
        
        self.menu.update(delta)
        if self.notification:
            self.notification.update(delta)

__app_export__ = SDHexpApp
