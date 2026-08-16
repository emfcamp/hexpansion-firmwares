# ir_rx.py Decoder for IR remote control using synchronous code
# IR_RX abstract base class for IR receivers.

# Author: Peter Hinch
# Copyright Peter Hinch 2020-2024 Released under the MIT license

# Thanks are due to @Pax-IT for diagnosing a problem with ESP32C3.

# Two capture strategies, chosen at construction:
#
# 1. esp32.RMTRX (preferred). The RMT peripheral records the whole pulse train
#    in hardware, immune to CPU load, and poll() collects it. This captures the
#    leading mark accurately, so every protocol decodes reliably.
# 2. Fallback for firmware without RMT RX: a single pin IRQ triggers on the
#    first edge of a block and a tight busy-poll records the transitions. This
#    avoids losing edges to scheduler latency, but the triggering edge is
#    consumed by the IRQ, so the leading mark is only approximate.
#
# Both fill self._times (edge times) and self.edge (count) for the decoders.

import micropython
from machine import Pin
from array import array
from utime import ticks_us, ticks_diff

try:
    from esp32 import RMTRX
except (ImportError, AttributeError):
    RMTRX = None

# True when the firmware provides hardware RMT RX capture. Protocols with short
# leader marks are only reliable when it is available, as the software fallback
# cannot time the leading edge accurately under host load.
HAVE_RMT_RX = RMTRX is not None


class IR_RX:
    # A gap this long (us) with no transition marks the end of a block. Must
    # exceed the longest space within any supported frame (NEC leader is 4.5ms)
    # and be far shorter than the interval to a repeat (~108ms). Fallback only.
    _gap_us = 6000

    # RMT RX capture settings. 1MHz resolution means the returned pulse widths
    # are microseconds, matching what the decoders expect.
    _rmt_resolution_hz = 1000000
    # Glitch filter; pulses shorter than this are ignored. The hardware register
    # is 8-bit so the ceiling is ~3187ns, far below any real IR pulse.
    _rmt_min_ns = 3000
    # A pulse longer than this ends the transaction. Must exceed the longest
    # in-frame pulse (NEC's 9ms leader mark, plus tolerance) and be shorter than
    # the gap to the next frame (~41ms before an NEC repeat).
    _rmt_max_ns = 15000000
    _rmt_num_symbols = 64

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

        self._rmt = None
        if RMTRX is not None:
            try:
                self._rmt = RMTRX(
                    pin=pin,
                    num_symbols=self._rmt_num_symbols,
                    min_ns=self._rmt_min_ns,
                    max_ns=self._rmt_max_ns,
                    resolution_hz=self._rmt_resolution_hz,
                )
                self._rmt.active(1)
            except Exception:
                # Unusable on this firmware/hardware: fall back to the pin IRQ.
                self._rmt = None
        if self._rmt is None:
            # One IRQ per block, on the leading (falling) edge. The receiver
            # idles high (pull-up) and pulls low for a mark.
            pin.irq(handler=self._cb_pin, trigger=Pin.IRQ_FALLING)

    # Collect a hardware-captured pulse train and decode it. Called periodically
    # by the app; a no-op when RMT RX is not in use.
    def poll(self):
        if self._rmt is None:
            return
        data = self._rmt.get_data()
        if not data:
            return
        # RMTRX returns signed pulse widths: positive high, negative low. A frame
        # begins with a mark, and the receiver idles high, so the first pulse
        # should be low. Skip a leading high pulse if one was captured.
        start = 1 if data[0] > 0 else 0
        count = len(data) - start
        # Rebuild the edge timeline the decoders expect: times[0] is the start of
        # the leading mark, each subsequent entry adds that pulse's width.
        times = self._times
        nedges = self._nedges
        times[0] = 0
        t = 0
        i = 0
        while i < count and i < nedges:
            d = data[start + i]
            t += -d if d < 0 else d
            times[i + 1] = t
            i += 1
        # Report the true count so an over-long train decodes as OVERRUN.
        self.edge = count + 1
        self.decode(None)

    # Pin interrupt (fallback): the block has started. Disable the IRQ so edges
    # during the capture cannot re-enter, busy-poll the frame, decode, re-arm.
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
        if self._rmt is not None:
            self._rmt.active(0)
            self._rmt.deinit()
            self._rmt = None
        else:
            self._pin.irq(handler=None)
