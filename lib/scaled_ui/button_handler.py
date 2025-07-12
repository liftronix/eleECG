import uasyncio as asyncio
from machine import Pin

class ButtonHandler:
    def __init__(self, pin_left, pin_right):
        self.left = Pin(pin_left, Pin.IN, Pin.PULL_UP)
        self.right = Pin(pin_right, Pin.IN, Pin.PULL_UP)

    async def listen(self, on_left, on_right, on_combo):
        combo = False
        while True:
            l = not self.left.value()
            r = not self.right.value()

            if l and not r:
                await on_left()
                await asyncio.sleep(0.3)

            elif r and not l:
                await on_right()
                await asyncio.sleep(0.3)

            elif l and r:
                if not combo:
                    combo = True
                    await asyncio.sleep(2)
                    if not self.left.value() and not self.right.value():
                        await on_combo()
                else:
                    pass
            else:
                combo = False

            await asyncio.sleep(0.05)