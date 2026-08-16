from app import App
from app_components import Menu, Notification, clear_background
import asyncio
import machine
from system.eventbus import eventbus
from system.scheduler.events import RequestForegroundPushEvent
import vfs

INSERTED = 0
REMOVED = 1

CARD_1_MOUNTPOINT = "/sdcard_1"
FORMAT_CARD_1 = "Format card 1"


class DualSdApp(App):
    def __init__(self, config):
        self._card_detect_slot_1 = config.ls_pin[0]
        self._card_detect_slot_1.init(self._card_detect_slot_1.IN)

        self._card_detect_slot_2 = config.ls_pin[3]
        self._card_detect_slot_2.init(self._card_detect_slot_2.IN)

        self._hex_config = config

        self._card_1 = None
        self._card_1_mounted = False

        self._card_1_present = self._card_detect_slot_1.value() == INSERTED
        self._card_2_present = self._card_detect_slot_2.value() == INSERTED

        self._notification = None
        self._foregrounded = False

        self._menu_items = self._build_menu_items()
        self._menu = Menu(
            self,
            self._menu_items,
            select_handler=self._select_handler,
            back_handler=self._back_handler,
        )

        super().__init__()

    def _refresh_menu_items(self):
        self._menu_items[:] = self._build_menu_items()

    def _build_menu_items(self):
        return [
            "Card 1: " + self._presence_text(self._card_1_present),
            "Card 2: " + self._presence_text(self._card_2_present),
            FORMAT_CARD_1,
        ]

    def _presence_text(self, present):
        if present:
            return "present"
        return "not present"

    async def background_task(self):
        slot_1_state = self._card_detect_slot_1.value()
        slot_2_state = self._card_detect_slot_2.value()
        self._card_1_present = None
        self._card_2_present = None

        while True:
            await asyncio.sleep(1)

            slot_1_state_now = self._card_detect_slot_1.value()
            slot_2_state_now = self._card_detect_slot_2.value()

            if slot_1_state != slot_1_state_now:
                slot_1_state = slot_1_state_now
                self._card_1_present = slot_1_state == INSERTED
                self._refresh_menu_items()

                if slot_1_state == INSERTED:
                    self._on_card_1_inserted()
                elif slot_1_state == REMOVED:
                    self._on_card_1_removed()

            if slot_2_state != slot_2_state_now:
                slot_2_state = slot_2_state_now
                self._card_2_present = slot_2_state == INSERTED
                self._refresh_menu_items()

                if slot_2_state == INSERTED:
                    self._on_card_2_inserted()
                elif slot_2_state == REMOVED:
                    self._on_card_2_removed()

    def _on_card_1_inserted(self):
        print("Card 1 inserted")

        if self._card_1_mounted:
            return

        try:
            self._card_1 = machine.SDCard(
                slot=3,
                width=1,
                sck=self._hex_config.pin[2],
                miso=self._hex_config.pin[3],
                mosi=self._hex_config.pin[1],
                cs=self._hex_config.pin[0],
            )
            vfs.mount(self._card_1, CARD_1_MOUNTPOINT)
            self._card_1_mounted = True
            self._notification = Notification("Card 1 mounted")
        except Exception as err:
            self._card_1 = None
            self._card_1_mounted = False
            self._notification = Notification("Card 1 mount failed: " + str(err))
            print("Card 1 mount failed", err)

    def _on_card_1_removed(self):
        print("Card 1 removed")

        if self._card_1_mounted:
            try:
                vfs.umount(CARD_1_MOUNTPOINT)
            except Exception as err:
                print("Card 1 unmount failed", err)

        self._card_1 = None
        self._card_1_mounted = False
        self._notification = Notification("Card 1 removed")

    def _on_card_2_inserted(self):
        print("Card 2 inserted")
        self._notification = Notification("Card 2 present")

    def _on_card_2_removed(self):
        print("Card 2 removed")
        self._notification = Notification("Card 2 removed")

    def _back_handler(self):
        self.minimise()

    def _select_handler(self, item, item_idx):
        if item != FORMAT_CARD_1:
            return

        try:
            self._format_card_1()
            self._notification = Notification("Card 1 formatted")
        except Exception as err:
            self._notification = Notification("Format failed: " + str(err))

    def _format_card_1(self):
        if not self._card_1_present:
            raise RuntimeError("no card")

        if self._card_1_mounted:
            vfs.umount(CARD_1_MOUNTPOINT)
            self._card_1_mounted = False

        if self._card_1 is None:
            self._card_1 = machine.SDCard(
                slot=3,
                width=1,
                sck=self._hex_config.pin[2],
                miso=self._hex_config.pin[3],
                mosi=self._hex_config.pin[1],
                cs=self._hex_config.pin[0],
            )

        vfs.VfsFat.mkfs(self._card_1)
        vfs.mount(self._card_1, CARD_1_MOUNTPOINT)
        self._card_1_mounted = True

    def draw(self, ctx):
        clear_background(ctx)
        self._menu.draw(ctx)
        if self._notification:
            self._notification.draw(ctx)

    def update(self, delta):
        if not self._foregrounded:
            eventbus.emit(RequestForegroundPushEvent(self))
            self._foregrounded = True

        self._menu.update(delta)
        if self._notification:
            self._notification.update(delta)


__app_export__ = DualSdApp
