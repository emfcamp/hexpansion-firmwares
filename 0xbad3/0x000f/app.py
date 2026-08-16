import app
import settings
import power


class PowerOffApp(app.App):
    def __init__(self, config):
        power.Off()


__app_export__ = PowerOffApp
