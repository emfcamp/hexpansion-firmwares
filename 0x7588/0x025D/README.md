# Dual uSD hexpansion

See https://github.com/DanNixon/microsd-hexpansion

If anyone more familiar with Micropython than I wants to try and get both slots working, then please go for it.
The two big issues I came across are:
- ePin is not a suitable CS pin for `SDCard`
- `SDCard` wants exclusive access to the SPI bus
