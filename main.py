import uasyncio as asyncio
import machine, gc, os, uos, time, logger, _thread
from machine import Pin
from core1_manager import core1_main, stop_core1
from shared_state import get_sensor_snapshot
from ota_manager import (
    get_local_version,
    apply_ota_if_pending,
    verify_ota_commit,
    check_and_download_ota
)

ota_lock = asyncio.Event()
ota_lock.set()  # Start with sensors enabled

from uthingsboard.client import TBDeviceMqttClient
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

'''
# 🛑 Safe Mode via GPIO14
safe_pin = Pin(14, Pin.IN, Pin.PULL_UP)
if not safe_pin.value():
    logger.warn("Safe Mode triggered — skipping OTA and main loop")
    import sys
    sys.exit()
'''

# 🔆 LED Setup
led = Pin('LED', Pin.OUT)
led.value(0)

# 📶 Wi-Fi Manager
wifi = WiFiManager(
    ssid=config.get("wifi", {}).get("ssid", ""),
    password=config.get("wifi", {}).get("password", "")
)
wifi.start()

#----------------------------------------------------------
# Memory and CPU Profiling
#----------------------------------------------------------
# --- Config ---
BASELINE_IDLE_TICKS = 8970       # Your measured 100% idle reference
MONITOR_INTERVAL = 5             # seconds between samples

# --- State ---
idle_counter = 0

# --- Idle Task ---
async def idle_task():
    global idle_counter
    while True:
        idle_counter += 1
        await asyncio.sleep_ms(0)

# --- CPU Utilization ---
def get_cpu_usage(idle_ticks):
    usage = max(0.0, (1 - idle_ticks / BASELINE_IDLE_TICKS)) * 100
    return f"🔥 CPU Active: {usage:.2f}%"

# --- Memory Monitor ---
def memory_usage(full=False):
    gc.collect()
    free_mem = gc.mem_free()
    allocated_mem = gc.mem_alloc()
    total_mem = free_mem + allocated_mem
    percent_free = '{:.2f}%'.format(free_mem / total_mem * 100)
    if full:
        return f"🧠 Memory - Total:{total_mem} Free:{free_mem} ({percent_free})"
    return percent_free

# --- Flash Monitor ---
def flash_usage():
    stats = uos.statvfs('/')
    block_size = stats[0]
    total_blocks = stats[2]
    free_blocks = stats[3]
    total = block_size * total_blocks
    free = block_size * free_blocks
    used = total - free
    percent_used = '{:.2f}%'.format(used / total * 100)
    return f"💾 Flash - Total:{total} Used:{used} ({percent_used})"

# --- System Monitor Task ---
async def monitor_resources():
    global idle_counter
    while True:
        snapshot = idle_counter
        await asyncio.sleep(MONITOR_INTERVAL)
        ticks = idle_counter - snapshot
        print(get_cpu_usage(ticks))
        print(memory_usage(full=True))
        print(flash_usage())
        print("—" * 40)

#----------------------------------------------------------


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


latest_sensor_data = {}
latest_sensor_lock = asyncio.Lock()

# 📤 Sensor Polling & Logging
async def drain_sensor_data(datalogger, ota_lock):
    last_seq = {}
    while True:
        await ota_lock.wait()  # ⛔ Block if OTA is active
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

                # Update global structure
                async with latest_sensor_lock:
                    latest_sensor_data[sensor] = {
                        'seq': current_seq,
                        'value': data,
                        'timestamp': time.ticks_ms()
                    }

                entry = f"[{sensor}] Seq={current_seq} → {data}"
                logger.debug(entry)
                await datalogger.log(entry)
        await asyncio.sleep_ms(1000)

# 🔦Laser Polling
async def drain_laser_data(laser, snapshot_ref, datalogger, ota_lock):
    while True:
        await ota_lock.wait()  # ⛔ Block if OTA is active
        try:
            snapshot = await laser.measure_and_log(tag="laser")
            snapshot_ref.clear()
            snapshot_ref.update(snapshot)

            seq = snapshot["seq"].get("laser")
            value = snapshot["payload"].get("laser")

            # Update global structure
            async with latest_sensor_lock:
                latest_sensor_data["laser"] = {
                    'seq': seq,
                    'value': value,
                    'timestamp': time.ticks_ms()
                }

            entry = f"[laser] Seq={seq} → {value}"
            await datalogger.log(entry)

        except Exception as e:
            logger.warn(f"Laser: Polling error — {e}")
        await asyncio.sleep_ms(1000)


# MQTT Publish
mqtt_seq_counter = 0

async def send_to_thingsboard(client, ota_lock):
    global mqtt_seq_counter
    while True:
        await ota_lock.wait()  # ⛔ Block if OTA is active
        status = wifi.get_status()
        if status['Internet'] != 'Connected':
            logger.warn("🚫 No Internet. Telemetry not sent.")
        else:
            try:
                client.connect()
                mqtt_seq_counter += 1

                # Read global snapshot safely
                async with latest_sensor_lock:
                    snapshot = latest_sensor_data.copy()

                # Package Telemetry Data
                payload = {
                    'Seq': str(mqtt_seq_counter),
                    'device_date': 'DATE',
                    'device_time': 'TIME'
                }

                for sensor, data in snapshot.items():
                    payload[f"{sensor}_seq"] = data['seq']
                    payload[f"{sensor}_value"] = data['value']

                client.send_telemetry(payload, qos=1)
                logger.debug(f"📤 Telemetry sent: {payload}")
                client.disconnect()
            except Exception as e:
                logger.error(f"⚠️ MQTT Publish Error: {e}")

        publish_interval = int(config.get("mqtt").get("publish_interval_sec"))
        await asyncio.sleep(max(5, publish_interval))


# 🚀 Main Entry Point
async def main():
    _thread.start_new_thread(core1_main, ())
    logger.info("🟢 Core 1 sensor sampling started.")

    led_blinker = LEDBlinker(pin_num='LED', interval_ms=200)
    led_blinker.start()
    
    asyncio.create_task(idle_task())       # Track idle time
    asyncio.create_task(monitor_resources())  # Start diagnostics
    
    logger.info(f"🧾 Running firmware version: {get_local_version()}")
    await apply_ota_if_pending(led)
    await verify_ota_commit(ota_lock)
    asyncio.create_task(check_and_download_ota(led, ota_lock))
    
    # SD Card and Data Logger
    sd = SDCardManager()
    await sd.mount()
    sync_config_if_changed()
    asyncio.create_task(sd.auto_manage())

    datalogger = DataLogger(sd, buffer_size=10, flush_interval_s=5)
    asyncio.create_task(datalogger.run())
    asyncio.create_task(drain_sensor_data(datalogger, ota_lock))
    
    # Laser
    laser = LaserModule()
    laser_snapshot = {}  # Shared container for latest laser data
    if not await laser.power_on():
        logger.error("Laser: Initialization failed")
    else:
        await laser.get_status()
        asyncio.create_task(drain_laser_data(laser, laser_snapshot, datalogger, ota_lock))
    
    #MQTT Initialization
    mqttHost = config.get("mqtt").get("host")
    mqttKey = config.get("mqtt").get("key")
    client = TBDeviceMqttClient(mqttHost, access_token = mqttKey)
    asyncio.create_task(send_to_thingsboard(client, ota_lock))
    
    while True:
        status = wifi.get_status()
        print(f"WiFi Status: {status['WiFi']}, Internet: {status['Internet']}")
        print(f"IP Address: {wifi.get_ip_address()}")
        if not ota_lock.is_set():
            logger.debug("📴 Sensor paused due to OTA activity")
        await asyncio.sleep(10)

# 🧹 Graceful Shutdown
try:
    asyncio.run(main())
except KeyboardInterrupt:
    logger.info("🔻 Ctrl+C detected — shutting down...")
    stop_core1()
    time.sleep(1)
    logger.info("🛑 System shutdown complete.")

