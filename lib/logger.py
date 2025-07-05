# logger.py

import time

class Logger:
    DEBUG_MODE = True
    INFO_MODE = True
    WARN_MODE = True
    ERROR_MODE = True

    _RESET = "\033[0m"
    _COLORS = {
        "DEBUG": "\033[90m",
        "INFO":  "\033[94m",
        "WARN":  "\033[93m",
        "ERROR": "\033[91m",
    }

    LOG_FILE = "/bootlog.txt"
    MAX_LOG_SIZE = 10 * 1024  # 10 KB

    @staticmethod
    def _write_log_file(level, msg):
        try:
            # Rotate log if needed
            if Logger._file_too_big():
                with open(Logger.LOG_FILE, "w") as f:
                    f.write("🗑 Log rotated due to size\n")
            ts = Logger._get_ts()
            with open(Logger.LOG_FILE, "a") as f:
                f.write(f"[{ts}] [{level}] {msg}\n")
        except:
            pass

    @staticmethod
    def _get_ts():
        try:
            return time.localtime()
        except:
            return time.time()

    @staticmethod
    def _file_too_big():
        try:
            return os.stat(Logger.LOG_FILE)[6] > Logger.MAX_LOG_SIZE
        except:
            return False

    @staticmethod
    def debug(msg):
        if Logger.DEBUG_MODE:
            print(f"{Logger._COLORS['DEBUG']}[DEBUG] {msg}{Logger._RESET}")
            Logger._write_log_file("DEBUG", msg)

    @staticmethod
    def info(msg):
        if Logger.INFO_MODE:
            print(f"{Logger._COLORS['INFO']}[INFO] {msg}{Logger._RESET}")
            Logger._write_log_file("INFO", msg)

    @staticmethod
    def warn(msg):
        if Logger.WARN_MODE:
            print(f"{Logger._COLORS['WARN']}[WARNING] {msg}{Logger._RESET}")
            Logger._write_log_file("WARNING", msg)

    @staticmethod
    def error(msg):
        if Logger.ERROR_MODE:
            print(f"{Logger._COLORS['ERROR']}[ERROR] {msg}{Logger._RESET}")
            Logger._write_log_file("ERROR", msg)

debug = Logger.debug
info = Logger.info
warn = Logger.warn
error = Logger.error
