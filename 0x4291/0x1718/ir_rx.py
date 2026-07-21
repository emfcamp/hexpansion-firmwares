# ir_rx.py Decoder for IR remote control using synchronous code
# IR_RX abstract base class for IR receivers.

# Author: Peter Hinch
# Copyright Peter Hinch 2020-2024 Released under the MIT license

# Thanks are due to @Pax-IT for diagnosing a problem with ESP32C3.

# Capture strategy for a busy host (the tildagon): a single pin IRQ triggers on
# the first edge of a block, then a tight busy-poll records every transition into
# self._times. This avoids losing edges to scheduler latency -- one soft IRQ per
# block instead of one per edge -- at the cost of blocking for the frame while it
# captures. The recorded times feed the existing decoders unchanged.

import micropython
from machine import Pin
from array import array
from utime import ticks_us, ticks_diff


class IR_RX:
    # A gap this long (us) with no transition marks the end of a block. Must
    # exceed the longest space within any supported frame (NEC leader is 4.5ms)
    # and be far shorter than the interval to a repeat (~108ms).
    _gap_us = 6000
    # Result/error codes
    # Repeat button code
    REPEAT = -1
    # Error codes
    BADSTART = -2
    BADBLOCK = -3
    BADREP = -4
    OVERRUN = -5
    BADDATA = -6
    BADADDR = -7

    def __init__(self, pin, nedges, tblock, callback, *args):  # Optional args for callback
        self._pin = pin
        self._nedges = nedges
        self._tblock = tblock
        self.callback = callback
        self.args = args
        self._errf = lambda _: None
        self.verbose = False

        self._times = array("i", (0 for _ in range(nedges + 1)))  # +1 for overrun
        self.edge = 0
        # One IRQ per block, on the leading (falling) edge. The receiver idles
        # high (pull-up) and pulls low for a mark, so a mark starts a block.
        pin.irq(handler=self._cb_pin, trigger=Pin.IRQ_FALLING)

    # Pin interrupt: the block has started. Disable the IRQ so edges during the
    # capture cannot re-enter, busy-poll the whole frame, decode, then re-arm.
    def _cb_pin(self, line):
        self._pin.irq(handler=None)
        self._capture()
        self.decode(None)
        self._pin.irq(handler=self._cb_pin, trigger=Pin.IRQ_FALLING)

    # Busy-poll the pin, recording the time of each transition. times[0] is the
    # (approximate) start, so times[1..] are the transitions after the edge that
    # triggered the IRQ -- matching what the per-edge scheme recorded.
    @micropython.native
    def _capture(self):
        times = self._times
        pin = self._pin
        nedges = self._nedges
        gap = self._gap_us
        maxus = self._tblock * 1000
        start = ticks_us()
        times[0] = start
        last = pin.value()
        last_change = start
        i = 1
        while i <= nedges:
            now = ticks_us()
            v = pin.value()
            if v != last:
                times[i] = now
                i += 1
                last = v
                last_change = now
            elif ticks_diff(now, last_change) > gap:
                break
            if ticks_diff(now, start) > maxus:
                break
        self.edge = i

    def do_callback(self, cmd, addr, ext, thresh=0):
        print("IR decode: edges", self.edge, "cmd", cmd, "addr", addr)  # DIAGNOSTIC
        self.edge = 0
        if cmd >= thresh:
            self.callback(cmd, addr, ext, *self.args)
        else:
            self._errf(cmd)

    def error_function(self, func):
        self._errf = func

    def close(self):
        self._pin.irq(handler=None)
