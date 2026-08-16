# LoRa Hexpansion

Hardware sources can be found at https://github.com/Stary2001/lora-hexpansion.

A hexpansion with a [HT-RA62](https://heltec.org/project/ht-ra62/) LoRa module.

## Pinout
MOSI: HS G
MISO: HS H
SCK: HS I
nCS: LS C
RXEN: LS B
BUSY: LS A
DIO1 (IRQ): HS F
nRST: LS D

There's also an active low LED on LS E because there was a spare GPIO.
