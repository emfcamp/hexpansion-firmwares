# InfraRed Hexpansion

This hexpansion receives infrared remote-control signals and decodes them into
button/address/command values. It contains an IR receiver and 5 neopixel LEDs.

## Default behaviour

The LEDs show a gradient built from your badge's two port bracket colours. The
number of LEDs lit acts as a "time since last signal" indicator: the longer it
has been since an IR frame was received, the fewer LEDs are lit. LED 0 is always
lit.

| Time since last signal | LEDs lit |
| ---------------------- | -------- |
| less than 1 second     | 5        |
| less than 10 seconds   | 4        |
| less than 100 seconds  | 3        |
| less than 1000 seconds | 2        |
| longer                 | 1        |

A freshly launched hexpansion begins minimally lit.

When a frame is received but fails to decode, the currently-lit LEDs flash red
for about 100ms, giving a quick indication of failed or corrupted reception.

## Reliability

Reliable IR reception is still being worked on. Decoding runs in software on a
busy host, so under load — for example while the screen reader is speaking or the
display is doing heavy rendering — some frames can be missed (a red LED flash
signals a dropped frame). Only the NEC schemes are enabled at present, as they
are the most robust; the Sony, Philips, Microsoft MCE and Samsung decoders are
temporarily disabled pending reliability improvements. Holding a button (which
sends repeats) is more reliable than a single quick tap.

## On-screen menu

Opening **InfraRed** from the launcher shows a menu. Use the badge **Up** /
**Down** buttons to scroll, **Confirm** to activate an item, and **Cancel** to
return to the background.

- **Encoding** — the selected IR standard. The **Next** button cycles through
  the supported standards. The selection is saved and restored on next launch:

  1. NEC 8-bit
  2. NEC 16-bit

- **Notifications** — when on, each decoded frame raises an on-screen
  notification. This setting is in-memory only and resets to off on each launch.
- **Send events** — when on, each decoded frame is emitted as an event for other
  apps to consume (see below). Saved between launches; on by default.
- **IR Control** — when on, decoded frames are turned into badge button presses
  (see below). Requires the NEC 8-bit encoding; it is saved between launches.

## Receiving signals in other apps

When **Send events** is enabled, each decoded frame is emitted as a `CustomEvent`
with the type `"ir_rx"`. The event data contains the `encoding` name and the
decoded `value`, `addr` and `ctrl` fields.

```python
from system.eventbus import eventbus
from events.custom import CustomEvent


def on_ir(event):
    if event.type != "ir_rx":
        return
    print(event["encoding"], event["value"], event["addr"], event["ctrl"])


eventbus.on(CustomEvent, on_ir, my_app)
```

`value` is the command (which button), `addr` is the device address (which
remote), and `ctrl` carries protocol-specific extra data (unused by the NEC
schemes, so currently always 0). A negative `value` is a status code rather than
a button (for example `-1` is an NEC repeat).

### Selecting the encoding

A remote is only decoded when the matching encoding standard is selected. As
well as using the **Next** button on screen, an app can set the standard
directly by name, which is saved and applied immediately:

```python
from system.hexpansion.util import get_app_by_vid_pid

ir_app = get_app_by_vid_pid(0x4291, 0x1718)
ir_app.select_encoding("NEC 16-bit")
```

The name must be one of the currently enabled standards:

- `NEC 8-bit`
- `NEC 16-bit`

An unrecognised name falls back to `NEC 8-bit`. The current standard is
available as `ir_app.encoding_name`.

## Using IR Control

**IR Control** lets an infrared remote drive the badge as if you were pressing
its buttons. It only works with the **NEC 8-bit** encoding; if a different
encoding is selected the toggle refuses to enable and shows a notification.
Changing the encoding away from NEC 8-bit turns IR Control back off.

Each of the badge's System and Frontboard buttons is emulated from an arbitrary
NEC 8-bit command code:

| Command code | Button        |
| ------------ | ------------- |
| 0            | Up            |
| 1            | Down          |
| 2            | Left          |
| 3            | Right         |
| 4            | Confirm       |
| 5            | Cancel        |
| 6 – 11       | Frontboard A–F |

When a matching frame is received a button-down is emitted. NEC sends repeat
codes while a key is held; the button stays down as long as repeats keep
arriving, and a button-up is emitted 200ms after the last frame.

### Flipper Zero remote

A ready-made remote for the [Flipper Zero](https://flipperzero.one/) is included
at [extras/tildagon.ir](extras/tildagon.ir), with one button per entry in the
table above. Copy it onto the Flipper (for example under `SD Card/infrared/`),
then in Infrared → Saved Remotes select it and send a button to drive the badge.

## Controlling the LEDs from other apps

This hexpansion allows other apps to take over its LEDs. The background
animation only drives the LEDs while `led_owner` is `None`, so set it to claim
ownership, then write to the `leds` attribute directly.

```python
from system.hexpansion.util import get_app_by_vid_pid

ir_app = get_app_by_vid_pid(0x4291, 0x1718)
ir_app.led_owner = ir_app  # any non-None value stops the animation

ir_app.leds[0] = (50, 0, 0)
ir_app.leds.write()
```

### Restoring the animation

Once you are no longer controlling the LEDs, please restore the animation:

```python
from system.hexpansion.util import get_app_by_vid_pid

ir_app = get_app_by_vid_pid(0x4291, 0x1718)
ir_app.led_owner = None
```

## Hardware

The IR receiver is read on the first hexpansion pin, and the 5 neopixel LEDs are
driven from the fourth. Point a standard consumer remote (TV, hi-fi, set-top
box) at the receiver and select the matching encoding standard to decode it.
