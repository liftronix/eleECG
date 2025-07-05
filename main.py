import uasyncio as asyncio
import machine, gc, os, time, logger, _thread
from machine import Pin
from core1_manager import core1_main, stop_core1
from shared_state import get_sensor_snapshot
from ota_manager import (
    get_local_version,
    apply_ota_if_pending,
    verify_ota_commit,
    check_and_download_ota
)
from ledblinker import LEDBlinker
from wifi_manager import WiFiManager
from sdcard_manager import SDCardManager
from datalogger import DataLogger
from laser_module import LaserModule
from config_loader import load_config

config = load_config()

# 🕒 REPL-safe boot delay
print("⏳ Boot delay... press Stop in Thonny to break into REPL")
time.sleep(3)

# 🛑 Safe Mode via GPIO14
safe_pin = Pin(14, Pin.IN, Pin.PULL_UP)
if not safe_pin.value():
    logger.warn("Safe Mode triggered — skipping OTA and main loop")
    import sys
    sys.exit()

# 🔆 LED Setup
led = Pin('LED', Pin.OUT)
led.value(0)

# 📶 Wi-Fi Manager
wifi = WiFiManager(
    ssid=config.get("wifi", {}).get("ssid", ""),
    password=config.get("wifi", {}).get("password", "")
)
wifi.start()

# 🧠 CPU Utilization Monitor
idle_counter = 0
async def idle_task():
    global idle_counter
    while True:
        idle_counter += 1
        await asyncio.sleep_ms(0)

async def monitor():
    global idle_counter
    while True:
        start = idle_counter
        await asyncio.sleep(1)
        ticks = idle_counter - start
        print(f"Utilization: {(1808 - ticks) / 1808 * 100:.2f} %")

# 🧮 Config Sync
def sync_config_if_changed(sd_path="/sd/config.json", flash_path="/config.json", file_name="config.json"):
    try:
        if file_name not in os.listdir("/sd"):
            logger.warn("No config.json found on SD card")
            return

        with open(sd_path, "rb") as f_sd:
            sd_data = f_sd.read()
        try:
            with open(flash_path, "rb") as f_flash:
                flash_data = f_flash.read()
        except OSError:
            flash_data = b""

        if sd_data != flash_data:
            with open(flash_path, "wb") as f:
                f.write(sd_data)
            logger.info("Updated config.json from SD card")
        else:
            logger.info("config.json is already up to date")
    except Exception as e:
        logger.error(f"Failed to sync config.json: {e}")

# 📤 Sensor Polling & Logging
async def drain_sensor_data(datalogger):
    last_seq = {}
    while True:
        snapshot = get_sensor_snapshot()
        if not snapshot or "payload" not in snapshot or "seq" not in snapshot:
            await asyncio.sleep_ms(100)
            continue

        seqs = snapshot["seq"]
        payloads = snapshot["payload"]

        for sensor, data in payloads.items():
            current_seq = seqs.get(sensor, -1)
            previous_seq = last_seq.get(sensor, -2)
            if current_seq != previous_seq:
                last_seq[sensor] = current_seq
                entry = f"[{sensor}] Seq={current_seq} → {data}"
                logger.debug(entry)
                await datalogger.log(entry)
        await asyncio.sleep_ms(100)

# Laser Polling
async def drain_laser_data(laser, snapshot_ref, datalogger):
    while True:
        try:
            snapshot = await laser.measure_and_log(tag="laser")
            snapshot_ref.clear()
            snapshot_ref.update(snapshot)

            # Persist to SD via datalogger
            seq = snapshot["seq"].get("laser")
            value = snapshot["payload"].get("laser")
            entry = f"[laser] Seq={seq} → {value}"
            await datalogger.log(entry)

        except Exception as e:
            logger.warn(f"Laser: Polling error — {e}")
        await asyncio.sleep_ms(500)

# 🚀 Main Entry Point
async def main():
    _thread.start_new_thread(core1_main, ())
    logger.info("🟢 Core 1 sensor sampling started.")

    led_blinker = LEDBlinker(pin_num='LED', interval_ms=2000)
    led_blinker.start()

    logger.info(f"🧾 Running firmware version: {get_local_version()}")
    await apply_ota_if_pending(led)
    await verify_ota_commit()

    asyncio.create_task(idle_task())
    asyncio.create_task(monitor())
    asyncio.create_task(check_and_download_ota(led))
    
    # SD Card and Data Logger
    sd = SDCardManager()
    await sd.mount()
    sync_config_if_changed()
    asyncio.create_task(sd.auto_manage())

    datalogger = DataLogger(sd, buffer_size=10, flush_interval_s=5)
    asyncio.create_task(datalogger.run())
    asyncio.create_task(drain_sensor_data(datalogger))
    
    # Laser
    laser = LaserModule()
    laser_snapshot = {}  # Shared container for latest laser data
    if not await laser.power_on():
        logger.error("Laser: Initialization failed")
    else:
        await laser.get_status()
        asyncio.create_task(drain_laser_data(laser, laser_snapshot, datalogger))

    while True:
        status = wifi.get_status()
        print(f"WiFi Status: {status['WiFi']}, Internet: {status['Internet']}")
        print(f"IP Address: {wifi.get_ip_address()}")
        await asyncio.sleep(10)

# 🧹 Graceful Shutdown
try:
    asyncio.run(main())
except KeyboardInterrupt:
    logger.info("🔻 Ctrl+C detected — shutting down...")
    stop_core1()
    time.sleep(1)
    logger.info("🛑 System shutdown complete.")