# platform_boot.py

import machine, time, logger
from machine import Pin, I2C, Timer
import ssd1306

# --- Internal State ---
uptime_s = 0
offline_time_s = 0
watch_dog_time_s = 0

sys_timer = None

# --- Power Pin ---
def init_power_pin(pin_num=2):
    """Sets the default power MOSFET pin HIGH"""
    Pin(pin_num, Pin.OUT).value(1)

# --- OLED Display ---
def init_display(scl=5, sda=4):
    """Initializes the SSD1306 OLED display"""
    i2c = I2C(0, scl=Pin(scl), sda=Pin(sda))
    try:
        oled = ssd1306.SSD1306_I2C(128, 64, i2c)
        oled.fill(0)
        oled.show()
        return oled
    except OSError as e:
        logger.error("OLED init error:", e)
        return None

# --- System Timer ---
def init_sys_timer(online_lock, reset_threshold=120):
    """Starts a periodic system timer for uptime and WDT logic"""
    
    def tick(timer):
        global uptime_s, offline_time_s, watch_dog_time_s

        uptime_s += 1
        watch_dog_time_s += 1

        if watch_dog_time_s > (reset_threshold - 10):
            logger.warn(f"Impending WatchDog Reset {reset_threshold - watch_dog_time_s}")
        if watch_dog_time_s > reset_threshold:
            logger.warn("Trigger WatchDog Reset")
            machine.reset()

        if not online_lock.is_set():
            offline_time_s += 1
    
    global sys_timer
    sys_timer = Timer()
    sys_timer.init(mode=Timer.PERIODIC, period=1000, callback=tick)
    return sys_timer

# --- Accessors ---
def get_uptime():
    return uptime_s

def get_offline_time():
    return offline_time_s

def get_watchdog_time():
    return watch_dog_time_s

def reset_watchdog_timer():
    global watch_dog_time_s
    watch_dog_time_s = 0

def deinit_sys_timer():
    global sys_timer
    if sys_timer:
        sys_timer.deinit()
        sys_timer = None
        logger.info("sys_timer Stopped")
