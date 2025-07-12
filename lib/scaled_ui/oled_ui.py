from scaled_ui.font_renderer import draw_text

class OLED_UI:
    def __init__(self, oled, sensors=None, scale=2):
        self.oled = oled
        self.sensors = sensors or []  # ensures it's always a list
        self.index = 0
        self.scale = scale

    async def next(self):
        sensor_count = len(self.sensors)
        if sensor_count == 0:
            draw_text(self.oled, "No sensor data yet", scale=self.scale)
            return
        self.index = (self.index + 1) % sensor_count
        await self._render_current()

    async def previous(self):
        sensor_count = len(self.sensors)
        if sensor_count == 0:
            draw_text(self.oled, "No sensor data yet", scale=self.scale)
            return
        self.index = (self.index - 1) % sensor_count
        await self._render_current()

    async def combo_action(self):
        draw_text(self.oled, "Special Mode Active", scale=self.scale)

    def show_message(self, msg, scale=None):
        draw_text(self.oled, msg, scale or self.scale)

    async def _render_current(self):
        try:
            fn = self.sensors[self.index]
            result = await fn()
            draw_text(self.oled, result, scale=self.scale)
        except Exception as e:
            draw_text(self.oled, f"Error: {str(e)}", scale=self.scale)