import uasyncio as asyncio
from machine import Pin
import time
import logger

class ButtonHandler:
    def __init__(self, pin_left, pin_right, long_press_ms=700):
        self.left = Pin(pin_left, Pin.IN, Pin.PULL_UP)
        self.right = Pin(pin_right, Pin.IN, Pin.PULL_UP)

        self.left_pressed_at = 0
        self.right_pressed_at = 0
        self.long_press_ms = long_press_ms

        self.ui = None

        # debounce tracking
        self.left_ready = True
        self.right_ready = True

    def attach_ui(self, ui):
        self.ui = ui

    def start(self):
        self.left.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self._handle_left)
        self.right.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self._handle_right)

    def _handle_left(self, pin):
        now = time.ticks_ms()
        if pin.value() == 0:  # button pressed
            self.left_pressed_at = now
        else:  # button released
            if not self.left_ready:
                return
            self.left_ready = False
            duration = time.ticks_diff(now, self.left_pressed_at)
            asyncio.create_task(self._process_event("left", duration))
            asyncio.create_task(self._debounce("left"))

    def _handle_right(self, pin):
        now = time.ticks_ms()
        if pin.value() == 0:
            self.right_pressed_at = now
        else:
            if not self.right_ready:
                return
            self.right_ready = False
            duration = time.ticks_diff(now, self.right_pressed_at)
            asyncio.create_task(self._process_event("right", duration))
            asyncio.create_task(self._debounce("right"))

    async def _process_event(self, side, duration):
        logger.debug(f"ButtonHandler → {side} press duration: {duration}ms")
        if not self.ui:
            logger.debug("ButtonHandler → No UI attached")
            return

        # Combo detection: both pressed now
        if not self.left.value() and not self.right.value():
            logger.debug("ButtonHandler → Combo detected")
            await self.ui.combo_action()
            return

        if duration >= self.long_press_ms:
            msg = f"{side} Long Press"
            logger.debug(f"ButtonHandler → Triggering show_message: {msg}")
            self.ui.show_message(msg)
        else:
            if side == "left":
                await self.ui.previous()
            else:
                await self.ui.next()

    async def _debounce(self, side):
        await asyncio.sleep_ms(300)
        if side == "left":
            self.left_ready = True
        else:
            self.right_ready = True
                    
if __name__ == "__main__":
    from scaled_ui.oled_ui import OLED_UI
    from scaled_ui.button_handler import ButtonHandler
    import ssd1306

    i2c = I2C(0, scl=Pin(5), sda=Pin(4))
    try:
        oled = ssd1306.SSD1306_I2C(128, 64, i2c)
        oled.fill(0)
        oled.show()
    except OSError as e:
        logger.error("OLED init error:", e)

    async def main():
        ui = OLED_UI(oled, scale=2)

        buttons = ButtonHandler(pin_left=6, pin_right=3)
        buttons.attach_ui(ui)
        buttons.start()

        # Just to keep loop alive
        while True:
            await asyncio.sleep(1)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🔻 Stopped manually.")