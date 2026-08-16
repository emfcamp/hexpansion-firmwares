# Hexpansion firmware updates for TeamRobotmad's hexpansions

# 0x2000 - HexSense

# 0x10c8 - HexDrive2

Software to drive the [HexDrive2](https://github.com/TeamRobotmad/HexDrive2), a 2 channel motor driver with distance and colour sensors hexpansion by [@robotmad](https://github.com/robotmad) and [@lincoltd7](https://github.com/lincoltd7).

# 0x2000 - HexAudio (Output Only)

I2S Audio output with a small loud speaker which can be used by any main Badge Application.

# 0x3000 - HexTest

Production test system for BadgeBot to measure the rotation rate of motors to enable the optimal pairs to be matched up.

# 0x4000 - HexDiag

For when you want to use a scope/logic analyser to measure timings or visualise low level diagnostics of what is going on within the badge.

# 0x5000 - HexCurrent

An adapted hexpansion interposer PCB with a current sensor in the 3V3 path from the badge to the Hexpansion Under Test (HUT).  The HexCurrent Hexpansion contains an INA226 I2C based current and voltage sensor for the purpose of measuring the current consumption of any hexpansion which is plugged into it.  The HexCurrent passes through all of the normal badge hexpansion connctor signals.  This is for use by fellow emf camp badge hexpansion developers who are interested in the current consumption of their hardware in real use particularly as there is a limit of around 600-700mA available to each hexpansion port on the badge.   Optionally the HexCurrent has a flying test lead that can be connected to any (test) point on the Hexpansion Under Test (HUT) to measure the voltage. e.g. if the HUT includes a voltage regulator or Switch Mode Power Supply the developer might want to check what the output is in real use cases. 
The companion App for this is also called “HexCurrent” and can be installed on an EEPROM (not fitted to the prototype hexpansion) or installed and run as a normal Badge App.  Actually, not having an EEPROM on the hexpansion means that the Badge sees the EEPROM on any hexpansion plugged into the HexCurrent.  This includes data capture of the current consumed by a hexpansion (and the votlage from one test point anywhere you choose), stored as a csv file and ploted on the display. [HexCurrent](https://github.com/TeamRobotmad/HexCurrent)

# 0x6000 - XYStage

A Microscope XY Stage controlled by EMF Badge using Joystick Hexpansion (below).

# 0x6001 - Joystick

4 switch joystick connected to the hexpansion HS pins.
 
> [!NOTE]
> For issues and pull requests, please use the original repos at https://github.com/TeamRobotmad
