# Caffeine Jitters Driver
## A.K.A. the cool drinking hat man hexpansion

This is the bare bones driver app for the Caffeine Jitters hexpansion.

It launches a simple background service, which responds to events from the eventbus, which are emitted by other apps.

Currently it responds to:
- `EmotePositiveEvent` with a long upwards ramp
- `EmoteNegativeEvent` with a long downwards ramp
- `dict` types emitted from the eventbus (see below)

This allows any app to add haptic feedback with just a couple of lines of extra code, without needing to scan for the hexpansion.

If you want something other than just the default positive and negative, you emit a custom `dict` event using the following:

```python
from system.eventbus import eventbus

eventbus.emit({"type":"haptic", "haptic_type": "YOUR_EFFECT_HERE", "duration" = 500})
```

Where `YOUR_EFFECT_HERE` is one of the following keywords, passed as a string:
- `click`
- `double_click`
- `double_click_long`
- `triple_click`
- `buzz`
- `tick`
- `ramp_up_medium`
- `ramp_up_short`
- `ramp_up_long`
- `ramp_down_short`
- `ramp_down_medium`
- `ramp_down_long`
- `continuous` (See below)
- `hum` (See below)

When using the `continuous` or `hum` haptic types, you need to specify the `duration` as well, in milliseconds. Leaving this parameter out will result in no response. For the other effects it can be omitted.


## The driver uses a very lightly modified port of Adafruit's DRV2605 library, I take absolutely no credit for any of the good work that's gone into it, only the bad work. Used and reproduced under the MIT License.

See here: https://docs.circuitpython.org/projects/drv2605/en/latest/api.html

See also the chip datasheet at https://www.ti.com/lit/ds/symlink/drv2605.pdf if you want to hack in some more events to your own version of the firmware, there's hundreds to play with and I've only included a small subset.
