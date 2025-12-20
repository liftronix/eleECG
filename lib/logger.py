'''
- 🟢 UART initializes only when used
- 🛑 UART stays disabled if UART_ENABLED = False
- 🎨 ANSI colors fully supported in PuTTY
- 💾 Switches for REPL, storage, UART control
- 🧼 CRLF (\r\n) for clean serial line break
- 💾 Saves log to on-chip flash
'''
import time
import os
import sys
from machine import UART, Pin

class Logger:
    # Log level controls
    DEBUG_MODE = False
    INFO_MODE = True
    WARN_MODE = True
    ERROR_MODE = True

    # Output toggles
    REPL_ENABLED = True
    STORAGE_ENABLED = False
    UART_ENABLED = True

    # UART instance (deferred setup)
    UART_PORT = None

    _RESET = "\033[0m"
    _COLORS = {
        "DEBUG": "\033[90m",
        "INFO":  "\033[94m",
        "WARN":  "\033[93m",
        "ERROR": "\033[91m",
    }

    LOG_FILE = "/bootlog.txt"
    MAX_LOG_SIZE = 100 * 1024  # 100 KB
    ROTATE_COUNTER_FILE = "/bootlog.iter"

    @staticmethod
    def _write_log_file(level, msg):
        try:
            if Logger._file_too_big():
                rotation_id = Logger._increment_rotation_counter()
                archived = Logger.LOG_FILE + ".old"
                try:
                    if Logger._file_exists(archived):
                        os.remove(archived)
                    os.rename(Logger.LOG_FILE, archived)
                except Exception as rotate_err:
                    sys.print_exception(rotate_err)

                with open(Logger.LOG_FILE, "w") as f:
                    f.write("🗂 Log rotated | Iteration #: {}\r\n".format(rotation_id))

            ts = Logger._get_ts()
            line = "[{}] [{}] {}\r\n".format(ts, level, msg)
            with open(Logger.LOG_FILE, "a") as f:
                f.write(line)
        except Exception as write_err:
            sys.print_exception(write_err)

    @staticmethod
    def _uart_log(level, msg):
        try:
            if Logger.UART_ENABLED:
                if Logger.UART_PORT is None:
                    Logger.UART_PORT = UART(1, baudrate=115200, tx=Pin(8), rx=Pin(9))
                color = Logger._COLORS.get(level, "")
                line = "{}[{}] {}{}\r\n".format(color, level, msg, Logger._RESET)
                Logger.UART_PORT.write(line)
        except Exception as uart_err:
            sys.print_exception(uart_err)

    @staticmethod
    def _get_ts():
        try:
            tm = time.localtime()
            return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                tm[0], tm[1], tm[2], tm[3], tm[4], tm[5]
            )
        except:
            return str(time.time())

    @staticmethod
    def _file_too_big():
        try:
            if not Logger._file_exists(Logger.LOG_FILE):
                return False
            return os.stat(Logger.LOG_FILE)[6] > Logger.MAX_LOG_SIZE
        except Exception as stat_err:
            sys.print_exception(stat_err)
            return False

    @staticmethod
    def _increment_rotation_counter():
        try:
            if not Logger._file_exists(Logger.ROTATE_COUNTER_FILE):
                with open(Logger.ROTATE_COUNTER_FILE, "w") as f:
                    f.write("1")
                return 1
            with open(Logger.ROTATE_COUNTER_FILE, "r+") as f:
                val = int(f.read().strip())
                f.seek(0)
                f.write(str(val + 1))
                return val + 1
        except Exception as count_err:
            sys.print_exception(count_err)
            return 0

    @staticmethod
    def _file_exists(path):
        try:
            folder = "/".join(path.split("/")[:-1]) or "."
            fname = path.split("/")[-1]
            return fname in os.listdir(folder)
        except:
            return False

    @staticmethod
    def debug(msg):
        if Logger.DEBUG_MODE:
            if Logger.REPL_ENABLED:
                print(f"{Logger._COLORS['DEBUG']}[DEBUG] {msg}{Logger._RESET}")
            if Logger.STORAGE_ENABLED:
                Logger._write_log_file("DEBUG", msg)
            Logger._uart_log("DEBUG", msg)

    @staticmethod
    def info(msg):
        if Logger.INFO_MODE:
            if Logger.REPL_ENABLED:
                print(f"{Logger._COLORS['INFO']}[INFO] {msg}{Logger._RESET}")
            if Logger.STORAGE_ENABLED:
                Logger._write_log_file("INFO", msg)
            Logger._uart_log("INFO", msg)

    @staticmethod
    def warn(msg):
        if Logger.WARN_MODE:
            if Logger.REPL_ENABLED:
                print(f"{Logger._COLORS['WARN']}[WARNING] {msg}{Logger._RESET}")
            if Logger.STORAGE_ENABLED:
                Logger._write_log_file("WARNING", msg)
            Logger._uart_log("WARNING", msg)

    @staticmethod
    def error(msg):
        if Logger.ERROR_MODE:
            if Logger.REPL_ENABLED:
                print(f"{Logger._COLORS['ERROR']}[ERROR] {msg}{Logger._RESET}")
            if Logger.STORAGE_ENABLED:
                Logger._write_log_file("ERROR", msg)
            Logger._uart_log("ERROR", msg)

# Aliases
debug = Logger.debug
info = Logger.info
warn = Logger.warn
error = Logger.error