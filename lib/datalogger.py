'''
✅ Buffered logging to preserve SD longevity
✅ Safe mount state checks to prevent write errors
✅ Hot-swap resilience for real-world user behavior
✅ Dynamic log rotation based on size
✅ Folder-per-day organization
'''
import uasyncio as asyncio
from simplequeue import Queue
import time
import os
from logger import Logger


class DataLogger:
    def __init__(self, sd_manager, log_dir="logs", prefix="log",
                 min_free_mb=5, buffer_size=10, flush_interval_s=5,
                 max_file_mb=2):
        self.sd = sd_manager
        self.log_dir = log_dir  # Top-level folder (e.g. 'logs')
        self.prefix = prefix    # File prefix (e.g. 'log')
        self.min_free_mb = min_free_mb  # Minimum free space before purge
        self.buffer_size = buffer_size  # Number of lines before flush
        self.flush_interval_s = flush_interval_s  # Max time between flushes
        self.max_file_bytes = max_file_mb * 1024 * 1024  # Rotate if file > 2MB

        self.queue = Queue()
        self._current_filename = None
        self._current_log_dir = None
        self._log_buffer = []
        self._last_flush_time = time.time()
        
        self._cached_free_space_mb = 9999  # Initial dummy value
        self._last_space_check = time.time()
        self.space_check_interval = 60  # seconds

        # 📁 Ensure base log directory exists at startup (required for rotation)
        try:
            if not self.sd.is_dir(self.log_dir):
                os.mkdir(self.sd._full_path(self.log_dir))
                Logger.info("Created base log directory: {}".format(self.log_dir))
        except Exception as e:
            Logger.error("Failed to create base log directory '{}': {}".format(self.log_dir, e))

    def _get_today_folder(self):
        # 📆 Creates path like: logs/2025-07-18/
        t = time.localtime()
        return "{}/{}-{:02d}-{:02d}".format(self.log_dir, t[0], t[1], t[2])

    def _rotate_filename(self):
        """
        Creates base log directory and per-day folder safely.
        Generates next filename based on existing .txt files.
        """
        # 🔧 Construct resolved paths
        base_dir = self.sd._full_path(self.log_dir)  # e.g., /sd/logs
        today_folder_name = self._get_today_folder().split("/")[-1]  # e.g., 2025-07-19
        today_dir = "{}/{}".format(base_dir, today_folder_name)      # e.g., /sd/logs/2025-07-19

        # 📁 Ensure base 'logs' directory exists
        if not self.sd.is_dir(self.log_dir):
            try:
                os.mkdir(base_dir)
                Logger.info("Created base log directory: {}".format(base_dir))
            except Exception as e:
                Logger.error("mkdir failed for base log dir: {}".format(e))
                return None

        # 📁 Ensure today's folder exists inside /sd/logs/
        if not self.sd.is_dir("{}/{}".format(self.log_dir, today_folder_name)):
            try:
                os.mkdir(today_dir)
                Logger.info("Created folder: {}".format(today_dir))
            except Exception as e:
                Logger.error("mkdir failed for daily folder: {}".format(e))
                return None

        # 🔁 Determine next file index
        relative_today_dir = "{}/{}".format(self.log_dir, today_folder_name)  # used for sd.list_files
        files = sorted([
            f for f in self.sd.list_files(relative_today_dir)
            if f.endswith(".txt")
        ])
        next_index = len(files) + 1

        # 📝 Final filename: logs/2025-07-19/log_N.txt
        filename = "{}/log_{}.txt".format(relative_today_dir, next_index)
        Logger.info("Rotated log to: {}".format(filename))
        return filename

    def _get_file_size(self, path):
        try:
            return os.stat(self.sd._full_path(path))[6]  # Returns size in bytes
        except:
            return 0

    def _purge_logs_if_low_space(self):
        """
        Purges oldest .txt files and removes empty folders.
        Assumes caller has already determined low space condition.
        Skips current active folder. Logs folder state for debug.
        """
        try:
            folders = [
                f for f in self.sd.list_files(self.log_dir)
                if self.sd.is_dir("{}/{}".format(self.log_dir, f))
            ]
        except Exception as e:
            Logger.error("Failed to scan log folders: {}".format(e))
            return

        active_folder = self._get_today_folder()

        # 🚮 Pass 1: delete files from inactive folders
        for folder in sorted(folders):
            if folder == active_folder:
                continue

            folder_path = "{}/{}".format(self.log_dir, folder)
            try:
                files = sorted([
                    f for f in self.sd.list_files(folder_path)
                    if f.endswith(".txt")
                ])
            except Exception as e:
                Logger.error("Failed to list files in '{}': {}".format(folder_path, e))
                continue

            while files and self._cached_free_space_mb < self.min_free_mb:
                old = files.pop(0)
                file_path = "{}/{}".format(folder_path, old)
                try:
                    os.remove(self.sd._full_path(file_path))
                    Logger.warn("Deleted old log: {}".format(file_path))
                except Exception as e:
                    Logger.error("File purge failed for '{}': {}".format(file_path, e))

        # 🧼 Pass 2: remove folders with no .txt files
        for folder in sorted(folders):
            if folder == active_folder:
                continue

            folder_path = "{}/{}".format(self.log_dir, folder)
            try:
                contents = self.sd.list_files(folder_path)
                txt_files = [f for f in contents if f.endswith(".txt")]
                Logger.debug("Folder '{}' contains {} .txt files".format(folder_path, len(txt_files)))

                if not txt_files:
                    os.rmdir(self.sd._full_path(folder_path))
                    Logger.warn("Removed empty folder: {}".format(folder_path))
            except Exception as e:
                Logger.error("Folder cleanup failed for '{}': {}".format(folder_path, e))
        

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

                    # 🌡️ Refresh free space every 60 seconds
                    if (now - self._last_space_check) >= self.space_check_interval:
                        self._cached_free_space_mb = self.sd.get_free_space_mb()
                        self._last_space_check = now
                        Logger.debug("SD space check: {:.2f} MB free".format(self._cached_free_space_mb))

                    # 🧹 Trigger purge only when space is below threshold
                    if self._cached_free_space_mb < self.min_free_mb:
                        self._purge_logs_if_low_space()

                    # 📁 Ensure today's folder is ready
                    self._current_log_dir = self._get_today_folder()

                    if not self.sd.is_dir(self._current_log_dir):
                        try:
                            os.mkdir(self.sd._full_path(self._current_log_dir))
                            Logger.info("Created folder: {}".format(self._current_log_dir))
                        except Exception as e:
                            Logger.error("mkdir failed for {}: {}".format(self._current_log_dir, e))
                            self._log_buffer.clear()
                            self._last_flush_time = now
                            continue

                    # 📄 Ensure filename is aligned with active folder
                    if (not self._current_filename or
                        not self._current_filename.startswith(self._current_log_dir)):
                        self._current_filename = self._rotate_filename()

                    # 🔁 Rotate file if size exceeds limit
                    current_size = self._get_file_size(self._current_filename)
                    if current_size >= self.max_file_bytes:
                        self._current_filename = self._rotate_filename()

                    # ✏️ Write buffered data to file
                    data = "\n".join(self._log_buffer) + "\n"
                    self.sd.write_file(self._current_filename, data, append=True, safe=False)

                    Logger.debug("Flushed {} log line(s) → {}".format(len(self._log_buffer), self._current_filename))
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
