'''
- Buffered logging to preserve SD longevity
- Safe mount state checks to prevent write errors
- Hot-swap resilience for real-world user behavior
'''
import uasyncio as asyncio
from simplequeue import Queue
import time
import os
from logger import Logger


class DataLogger:
    def __init__(self, sd_manager, log_dir="logs", prefix="log",
                 min_free_mb=5, buffer_size=10, flush_interval_s=5):
        self.sd = sd_manager
        self.log_dir = log_dir
        self.prefix = prefix
        self.min_free_mb = min_free_mb
        self.buffer_size = buffer_size
        self.flush_interval_s = flush_interval_s

        self.queue = Queue()
        self._current_filename = None
        self._log_buffer = []
        self._last_flush_time = time.time()

    def _get_today_filename(self):
        t = time.localtime()
        return "{}/{}_{}-{:02d}-{:02d}.txt".format(
            self.log_dir, self.prefix, t[0], t[1], t[2])

    def _ensure_log_dir(self):
        if not self.sd.is_dir(self.log_dir):
            try:
                os.mkdir(self.sd._full_path(self.log_dir))
                Logger.info("Created log directory: {}".format(self.log_dir))
            except Exception as e:
                Logger.error("mkdir failed: {}".format(e))

    def _purge_logs_if_low_space(self):
        if self.sd.get_free_space_mb() >= self.min_free_mb:
            return
        files = sorted([f for f in self.sd.list_files(self.log_dir) if f.endswith(".txt")])
        while files and self.sd.get_free_space_mb() < self.min_free_mb:
            old = files.pop(0)
            try:
                os.remove(self.sd._full_path("{}/{}".format(self.log_dir, old)))
                Logger.warn("Deleted old log: {}".format(old))
            except Exception as e:
                Logger.error("Purge failed for '{}': {}".format(old, e))

    async def log(self, line):
        await self.queue.put(line)

    async def run(self):
        while True:
            try:
                line = await self.queue.get()
                self._log_buffer.append(line)

                now = time.time()
                buffer_full = len(self._log_buffer) >= self.buffer_size
                timeout_exceeded = (now - self._last_flush_time) >= self.flush_interval_s

                if buffer_full or timeout_exceeded:
                    if not self.sd.mounted:
                        Logger.warn("SD not mounted — skipping flush")
                        self._log_buffer.clear()
                        self._last_flush_time = now
                        continue

                    self._ensure_log_dir()
                    self._purge_logs_if_low_space()

                    filename = self._get_today_filename()
                    if filename != self._current_filename:
                        Logger.info("Switched to new log file: {}".format(filename))
                        self._current_filename = filename

                    data = "\n".join(self._log_buffer) + "\n"
                    self.sd.write_file(self._current_filename, data, append=True, safe=False)

                    Logger.debug("Flushed {} log line(s)".format(len(self._log_buffer)))
                    self._log_buffer.clear()
                    self._last_flush_time = now

            except Exception as e:
                Logger.error("Logging error in run(): {}".format(e))
                await asyncio.sleep(1)

if __name__ == "__main__":
    import uasyncio as asyncio
    import time
    from sdcard_manager import SDCardManager
    from datalogger import DataLogger
    from logger import Logger
    
    # --- Periodic Log Task ---
    async def periodic_data_capture(datalogger):
        while True:
            t_ms = time.ticks_ms()
            msg = "Sensor reading at t={} ms".format(t_ms)
            await datalogger.log(msg)
            Logger.debug("Queued: {}".format(msg))
            await asyncio.sleep(1)


    # --- Main Entry Point ---
    async def main():
        Logger.info("🧾 Starting system...")

        sd = SDCardManager(cs_pin=17, sck=18, mosi=19, miso=16, cd_pin=20)
        asyncio.create_task(sd.auto_manage())  # handles hot-swap and debounce

        datalogger = DataLogger(sd, buffer_size=10, flush_interval_s=5)
        asyncio.create_task(datalogger.run())
        asyncio.create_task(periodic_data_capture(datalogger))

        while True:
            await asyncio.sleep(10)


    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        Logger.info("Shutting down gracefully...")
