import app
import asyncio
import time

from events import Event
from system.eventbus import eventbus
from machine import UART, Pin


class GPSApp(app.App):
    """Provides a GPS API for apps to use directly and GPS Events that other apps may subscribe to."""

    VERSION = 3 # Increment this when making changes to the app that require the hexpansion app to be re-flashed with the new code.

    class GPSEvent(Event):
        def __init__(self, position, speed, bearing):
            self.position = position
            self.speed = speed
            self.bearing = bearing

        def __str__(self):
            return f"GPS fix {self.position}, speed {self.speed} knots, bearing {self.bearing}°"

    def __init__(self, config=None):
        super().__init__()

        # Config is mandatory, we're running from the EEPROM
        if config is None:
            raise TypeError
        self.config = config

        # GPS fix data
        self._position = None
        self._bearing = 0.0
        self._speed = 0.0

        # Ring buffer of recent raw NMEA sentences (checksum stripped), so apps
        # can parse additional sentence types (GGA/GSV/GSA) themselves
        self._lines = []

        # Specifying a small time out to wait before giving up on receiving
        # more characters ensures we always read full messages from the UART
        # This reduces parse errors due to only having half a message
        self.to = 10
        self.uart = UART(1, baudrate=9600, tx=config.pin[0], rx=config.pin[1], timeout=self.to)

        # Reset pin
        self.r = config.pin[2]
        self.r.init(mode=Pin.OUT)
        self.r.value(1)

        # Time since last valid GPS fix
        self.z = 0

    @property
    def position(self):
        """Position as a (latitude, longitude) tuple"""
        return self._position

    @property
    def bearing(self):
        """Course over ground in degrees from true north"""
        return self._bearing

    @property
    def speed(self):
        """Ground speed in knots"""
        return round(self._speed, 2)

    @property
    def sentences(self):
        """Recent raw NMEA sentences (checksum stripped) for apps to parse"""
        return list(self._lines)

    async def background_task(self):
        """Override the default background task behaviour to give more time to other apps"""
        last = time.ticks_ms()
        while True:
            start = time.ticks_ms()
            delta = time.ticks_diff(start, last)
            result = self.background_update(delta)
            # Get successive messages fast, but yield more time to other apps
            # if there was nothing to read, this lowers the frequency of
            # occurrances of blocking for the full read timeout to elapse when
            # nothing is being sent over the UART
            await asyncio.sleep_ms(25 if result else 250 - self.to)
            last = start

    def background_update(self, delta):
        self.z += delta

        # Delay releasing the reset pin a little bit
        if self.r.value():
            if self.z > 99:
                self.r.value(0)

        # Clear fix data if we haven't had a fix for a while
        if self._position:
            if self.z > 9999:
                self._position = None
                self._speed = 0

        l = self.uart.readline()
        if l:
            try:
                line = l.decode().strip()

                # Buffer the raw sentence so apps can parse other message types
                self._lines.append(line.split('*')[0])
                if len(self._lines) > 40:
                    self._lines = self._lines[-40:]

                p = line.split(',')
                if p[0] == "$GPRMC" or p[0] == "$GNRMC":
                    if p[2] == "A":
                        lat = float(p[3][:2]) + float(p[3][2:]) / 60
                        lon = float(p[5][:3]) + float(p[5][3:]) / 60
                        if p[4] == "S":
                            lat = -lat
                        if p[6] == "W":
                            lon = -lon
                        self._position = (round(lat, 5), round(lon, 5))
                        self._speed = float(p[7])
                        self._bearing = float(p[8])

                        # Eliminate satellite jitter when stationary by rounding
                        # very small velocities to zero
                        if self._speed < 1:
                            self._speed = 0

                        # Reset the time since last fix if we successfully got a valid fix message
                        self.z = 0

                    # Send event to subscribers
                    eventbus.emit(self.GPSEvent(self._position, self._speed, self._bearing))
            except (UnicodeError, ValueError, AttributeError, IndexError):
                pass
            return True
        return False


__app_export__ = GPSApp # pylint: disable=invalid-name
