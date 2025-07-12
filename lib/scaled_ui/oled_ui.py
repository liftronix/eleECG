import logger
from scaled_ui.font_renderer import draw_text

class OLED_UI:
    def __init__(self, oled, sensors=None, scale=2):
        self.oled = oled
        self.sensors = sensors or []
        self.index = 0
        self.scale = scale

    async def next(self):
        sensor_count = len(self.sensors)
        if sensor_count == 0:
            logger.debug("UI → next(): No sensor data available")
            draw_text(self.oled, "No sensor data yet", scale=self.scale)
            return
        self.index = (self.index + 1) % sensor_count
        logger.debug(f"UI → next(): Moving to sensor index {self.index}")
        await self._render_current()

    async def previous(self):
        sensor_count = len(self.sensors)
        if sensor_count == 0:
            logger.debug("UI → previous(): No sensor data available")
            draw_text(self.oled, "No sensor data yet", scale=self.scale)
            return
        self.index = (self.index - 1) % sensor_count
        logger.debug(f"UI → previous(): Moving to sensor index {self.index}")
        await self._render_current()

    async def combo_action(self):
        logger.debug("UI → combo_action(): Activating special mode")
        draw_text(self.oled, "Special Mode Active", scale=self.scale)

    def show_message(self, msg, scale=None):
        logger.debug(f"UI → show_message(): {msg}")
        draw_text(self.oled, msg, scale or self.scale)

    async def _render_current(self):
        if not self.sensors or len(self.sensors) == 0:
            logger.debug("UI → _render_current(): No sensor functions available")
            draw_text(self.oled, "No sensor data yet", scale=self.scale)
            return
        try:
            fn = self.sensors[self.index]
            result = await fn()
            logger.debug(f"UI → _render_current(): Rendering → {result}")
            draw_text(self.oled, result, scale=self.scale)
        except Exception as e:
            logger.debug(f"UI → _render_current(): Render error → {e}")
            draw_text(self.oled, f"Error: {str(e)}", scale=self.scale)