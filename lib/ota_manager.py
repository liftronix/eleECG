# 📁 ota_manager.py
import machine, os, gc, asyncio
import logger
from ota import OTAUpdater
from scaled_ui.oled_ui import OLED_UI

REPO_URL = "https://raw.githubusercontent.com/liftronix/eleECG/refs/heads/main"
MIN_FREE_MEM = 100 * 1024
FLASH_BUFFER = 16 * 1024

def get_local_version():
    try:
        with open("/version.txt") as f:
            return f.read().strip()
    except:
        return "0.0.0"
    
#---------------------------------------
def has_enough_memory():
    gc.collect()
    return gc.mem_free() >= MIN_FREE_MEM

#---------------------------------------
def get_free_flash_bytes():
    stats = os.statvfs("/")
    return stats[0] * stats[3]

#---------------------------------------
async def show_progress(ota, led, display):
    while ota.get_progress() < 100:
        led.toggle()
        logger.info(f"OTA {ota.get_progress():>3}% - {ota.get_status()}")
        display.show_message(f"OTA {ota.get_progress():>3}% - {ota.get_status()}")
        await asyncio.sleep(0.4)
    led.value(1)
    
#---------------------------------------
async def apply_ota_if_pending(led):
    if "ota_pending.flag" not in os.listdir("/"):
        return
    logger.info("🟡 ota_pending.flag detected — applying OTA update")
    ota = OTAUpdater(REPO_URL)
    if await ota.apply_update():
        logger.info("🔁 OTA applied successfully. Rebooting...")
        machine.reset()
    else:
        logger.error("❌ OTA apply failed. Rolling back.")
        await ota.rollback()
        ota.cleanup_flags()

#---------------------------------------
async def verify_ota_commit(ota_lock, display):
    updater = OTAUpdater(REPO_URL)

    if "ota_commit_pending.flag" not in os.listdir("/"):
        return  # No verification needed

    logger.info("🔎 Verifying OTA commit...")
    max_attempts = 12
    attempts = 0

    ota_lock.clear()  # Pause sensor/telemetry tasks

    try:
        while attempts < max_attempts:
            logger.info(f"Attempt {attempts}/{max_attempts} — waiting to verify OTA commit...")
            
            try:
                is_update = await updater.check_for_update()
                local = await updater._get_local_version()
                remote = updater.remote_version
                logger.info(f"OTA → Local: {local} | Remote: {remote}")

                if local == remote:
                    updater.cleanup_flags()
                    logger.info("✅ OTA commit verified. Flag removed.")
                    display.show_message(f"Verify\nSuccess")
                    return
            except Exception as e:
                logger.warn(f"Commit verify error: {e}")
                display.show_message(f"Verify\nError")

            attempts += 1
            await asyncio.sleep(5)

        # Too many failures — rollback now
        logger.warn("❌ Commit verification failed. Rolling back firmware.")
        display.show_message(f"Verify\nError")
        await updater.rollback()
        updater.cleanup_flags()
    except Exception as e:
        logger.warn(f"Commit verify error: {e}")
        
    finally:
        ota_lock.set()  # Resume sensor tasks
        
#---------------------------------------
async def check_and_download_ota(led, ota_lock, display, connection):
    updater = OTAUpdater(REPO_URL)
    while True:
        if connection['Internet'] != 'Connected':
            logger.warn("🚫 No Internet. Skipping OTA Check.")
        else:    
            logger.info("🔍 Checking for OTA update...")
            if await updater.check_for_update():
                logger.info("🆕 Update available.")
                if has_enough_memory():
                    required = updater.get_required_flash_bytes()
                    free = get_free_flash_bytes()
                    if free < required + FLASH_BUFFER:
                        logger.warn("🚫 Not enough flash space.")
                    else:
                        logger.info("📥 Downloading update...")
                        ota_lock.clear()  # 🚫 Pause sensors
                        try:
                            progress_task = asyncio.create_task(show_progress(updater, led, display))
                            if await updater.download_update():
                                progress_task.cancel()
                                led.value(1)
                                with open("/ota_pending.flag", "w") as f:
                                    f.write("ready")
                                for i in range(10, 0, -1):
                                    print(f"Rebooting in {i} seconds...")
                                    display.show_message(f"Reboot\n{i} sec")
                                    await asyncio.sleep(1)
                                machine.reset()
                            else:
                                progress_task.cancel()
                                led.value(0)
                                logger.error("❌ Download failed.")
                        finally:
                            ota_lock.set()  # ✅ Resume sensors
                else:
                    logger.warn("🚫 Not enough memory for OTA.")
            else:
                logger.info("✅ Firmware is up to date.")
                await asyncio.sleep(600)        
        #yeild        
        await asyncio.sleep(60)
