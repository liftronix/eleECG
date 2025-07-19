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
async def show_progress(ota, led_blinker, display):
    while ota.get_progress() < 100:
        led_blinker.set_interval(100)
        logger.info(f"OTA {ota.get_progress():>3}% - {ota.get_status()}")
        display.show_message(f"OTA {ota.get_progress():>3}% - {ota.get_status()}")
        await asyncio.sleep(0.4)
    led_blinker.set_interval(500)
    
#---------------------------------------
async def apply_ota_if_pending(led_blinker):
    if "ota_pending.flag" not in os.listdir("/"):
        return
    logger.info("🟡 ota_pending.flag detected — applying OTA update")
    ota = OTAUpdater(REPO_URL)
    led_blinker.set_interval(100)
    if await ota.apply_update():
        logger.info("🔁 OTA applied successfully. Rebooting...")
        machine.reset()
    else:
        logger.error("❌ OTA apply failed. Rolling back.")
        await ota.rollback()
        ota.cleanup_flags()
    led_blinker.set_interval(500)

#---------------------------------------
async def verify_ota_commit(online_lock, ota_lock, display):
    updater = OTAUpdater(REPO_URL)

    if "ota_commit_pending.flag" not in os.listdir("/"):
        return  # No verification needed

    logger.info("🔎 Verifying OTA commit...")
    max_attempts = 12
    attempts = 0

    ota_lock.clear()  # 🚫 Pause Sensing during verification

    try:
        while attempts < max_attempts:
            logger.info(f"Attempt {attempts+1}/{max_attempts} — OTA commit check")
            display.show_message(f"Verify\nTry {attempts+1}")

            # Wait for internet lock — if fails, retry
            try:
                await asyncio.wait_for(online_lock.wait(), timeout=5)
            except asyncio.TimeoutError:
                logger.warn("🕸️ Internet not ready — will retry")
                display.show_message("Verify\nNo WiFi")
                attempts += 1
                await asyncio.sleep(5)
                continue  # retry loop

            # Try OTA version comparison
            try:
                is_update = await asyncio.wait_for(updater.check_for_update(), timeout=5)
                local = await updater._get_local_version()
                remote = updater.remote_version
                logger.info(f"OTA → Local: {local} | Remote: {remote}")

                if local == remote:
                    updater.cleanup_flags()
                    logger.info("✅ OTA commit verified. Flag removed.")
                    display.show_message("Verify\nSuccess")
                    return
                else:
                    logger.warn("🔁 Version mismatch — OTA commit pending")
                    display.show_message("Verify\nMismatch")

            except asyncio.TimeoutError:
                logger.warn("⚠️ OTA check timed out.")
                display.show_message("Verify\nTimeout")
            except Exception as e:
                logger.warn(f"Commit verify error: {e}")
                display.show_message("Verify\nError")

            attempts += 1
            await asyncio.sleep(5)

        # ⏱️ Max attempts exhausted — rollback
        logger.warn("❌ Commit verification failed. Rolling back firmware.")
        display.show_message("Verify\nRollback")
        await updater.rollback()
        updater.cleanup_flags()

    except Exception as e:
        logger.warn(f"🚨 Unhandled commit verify error: {e}")
        display.show_message("Verify\nException")

    finally:
        ota_lock.set()  # ✅ Resume Sensing tasks

        
#---------------------------------------
async def check_and_download_ota(led_blinker, ota_lock, display, online_lock):
    updater = OTAUpdater(REPO_URL)
    while True:
        try:
            await asyncio.wait_for(online_lock.wait(), timeout=20)# Block if device is offline
        
            logger.info("🔍 Checking for OTA update...")
            if await updater.check_for_update():
                logger.info("🆕 Update available.")
                led_blinker.set_interval(100)
                if has_enough_memory():
                    required = updater.get_required_flash_bytes()
                    free = get_free_flash_bytes()
                    if free < required + FLASH_BUFFER:
                        logger.warn("🚫 Not enough flash space.")
                    else:
                        logger.info("📥 Downloading update...")
                        ota_lock.clear()  # 🚫 Pause sensors
                        try:
                            progress_task = asyncio.create_task(show_progress(updater, led_blinker, display))
                            if await updater.download_update():
                                progress_task.cancel()
                                with open("/ota_pending.flag", "w") as f:
                                    f.write("ready")
                                for i in range(10, 0, -1):
                                    print(f"Rebooting in {i} seconds...")
                                    display.show_message(f"Reboot\n{i} sec")
                                    await asyncio.sleep(1)
                                machine.reset()
                            else:
                                progress_task.cancel()
                                logger.error("❌ Download failed.")
                        finally:
                            ota_lock.set()  # ✅ Resume sensors
                            led_blinker.set_interval(500)
                else:
                    logger.warn("🚫 Not enough memory for OTA.")
            else:
                logger.info("✅ Firmware is up to date.")
                
        except asyncio.TimeoutError:
            logger.warn("⏳ Online check timed out — skipping OTA this round")            
        
        await asyncio.sleep(120)
