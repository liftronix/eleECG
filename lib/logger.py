import time
import os
import sys

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
    ROTATE_COUNTER_FILE = "/bootlog.iter"

    @staticmethod
    def _write_log_file(level, msg):
        try:
            if Logger._file_too_big():
                rotation_id = Logger._increment_rotation_counter()
                archived = Logger.LOG_FILE + ".old"
                try:
                    if os.exists(archived):
                        os.remove(archived)
                    os.rename(Logger.LOG_FILE, archived)
                except Exception as rotate_err:
                    sys.print_exception(rotate_err)

                with open(Logger.LOG_FILE, "w") as f:
                    f.write("🗂 Log rotated | Iteration #: {}\n".format(rotation_id))

            ts = Logger._get_ts()
            with open(Logger.LOG_FILE, "a") as f:
                f.write("[{}] [{}] {}\n".format(ts, level, msg))
        except Exception as write_err:
            sys.print_exception(write_err)

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
            return os.stat(Logger.LOG_FILE)[6] > Logger.MAX_LOG_SIZE
        except Exception as stat_err:
            sys.print_exception(stat_err)
            return False

    @staticmethod
    def _increment_rotation_counter():
        try:
            if not os.exists(Logger.ROTATE_COUNTER_FILE):
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

# Export aliases
debug = Logger.debug
info = Logger.info
warn = Logger.warn
error = Logger.error