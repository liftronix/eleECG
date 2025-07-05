# ledblinker.py

import uasyncio as asyncio
from machine import Pin

class LEDBlinker:
    def __init__(self, pin_num, interval_ms=500):
        self.led = Pin(pin_num, Pin.OUT)
        self.interval = interval_ms
        self._task = None
        self._running = False

    def set_interval(self, ms):
        """Change blink interval on-the-fly"""
        self.interval = ms

    async def _blink(self):
        while self._running:
            self.led.toggle()
            await asyncio.sleep_ms(self.interval)

    def start(self):
        """Begin blinking loop"""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._blink())

    def stop(self):
        """Stop blinking"""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        self.led.value(0)  # Turn off LED when stopping

if __name__ == "__main__":
    import uasyncio as asyncio
    #from ledblinker import LEDBlinker

    led = LEDBlinker(pin_num=25, interval_ms=300)
    led.start()

    async def main():
        await asyncio.sleep(5)
        led.set_interval(100)  # Speed up
        await asyncio.sleep(5)
        led.stop()

    asyncio.run(main())
