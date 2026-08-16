# Map Hexpansion

This hexpansion is a stylised view of the UK and Ireland, made with neopixel LEDs. It contains 76 LEDs and two buttons.

## Default behaviour

This shows the Rainbow LED pattern. Button A will cycle the brightness, between 0% and 25%.

Button B will cycle the alignment of the LEDs, between the following options:

1. North / South
2. East / West
3. Coast / Inland
4. Northwest / Southeast
5. Northeast / Southwest
6. Single string

## Control through other apps

This hexpansion allows you to take over control of the LEDs as part of other apps. To do this, you will need to get the app object and disable the pattern running behaviour.

At that point you can control the LEDs manually through the `inner_leds` attribute.

```python
from system.hexpansion.util import get_app_by_vid_pid

map_app = get_app_by_vid_pid(0x4291, 0x1830)
map_app.leds_running = False

map_app.inner_leds.fill((50, 0, 0))
map_app.inner_leds.write()
```

### Using the built-in groupings

You can also control the LEDs in one of the above alignments, by setting alignment, calling a setup method, then accessing the `leds` attribute.

```python
import random
from system.hexpansion.util import get_app_by_vid_pid

map_app = get_app_by_vid_pid(0x4291, 0x1830)
map_app.leds_running = False

map_app.setup_led_group('coastal')

for index in range(map_app.leds.n):
    map_app.leds[index] = random.randint(0, 50), random.randint(0, 50), random.randint(0, 50)

map_app.leds.write()
```

### Marking places

When using `inner_leds` rather than a grouping pattern, you can also address LEDs by latitude/longitude using the built-in `clear_locations` and `mark_location` methods.

```python
from system.hexpansion.util import get_app_by_vid_pid

map_app = get_app_by_vid_pid(0x4291, 0x1830)
map_app.clear_locations()

map_app.mark_location(52, 0, (255, 0, 0))
```

### Restoring the pattern

Once you are no longer controlling the LEDs, please restore the pattern:


```python
from system.hexpansion.util import get_app_by_vid_pid

map_app = get_app_by_vid_pid(0x4291, 0x1830)
map_app.leds_running = True
```

## Power usage

The hexpansion cannot power all LEDs at full brightness. The _average_ value for each channel across all LEDs should not exceed 50. If you exceed this, the voltage will sag, a high-pitched noise will be emitted, and brightness will fail to increase.

You can either manage this manually, or wrap the LED in a correction factor if you need a string that acts transparently like normal NeoPixels:

```python
import neopixel
from system.hexpansion.util import get_app_by_vid_pid

map_app = get_app_by_vid_pid(0x4291, 0x1830)
map_app.leds_running = False

corrected_leds = neopixel.CorrectedNeoPixel(
    map_app.inner_leds,
    [neopixel.DimCorrection(0.2)] * map_app.inner_leds.n
)
corrected_leds.fill((255, 255, 255))
corrected_leds.write()
```

This can also be applied to the `leds` style combined access approach.

## Hardware

The hardware designs are available at https://github.com/MatthewWilkes/uk-map-hexpansion
