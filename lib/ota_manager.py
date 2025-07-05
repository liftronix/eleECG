# 📁 ota_manager.py
import machine, os, gc, asyncio
import logger
from ota import OTAUpdater

REPO_URL = "https://raw.githubusercontent.com/liftronix/eleECG/refs/heads/main"
MIN_FREE_MEM = 100 * 1024
FLASH_BUFFER = 16 * 1024

def get_local_version():
    try:
        with open("/version.txt") as f:
            return f.read().strip()
    except:
        return "0.0.0"

def has_enough_memory():
    gc.collect()
    return gc.mem_free() >= MIN_FREE_MEM

def get_free_flash_bytes():
    stats = os.statvfs("/")
    return stats[0] * stats[3]

async def show_progress(ota, led):
    while ota.get_progress() < 100:
        led.toggle()
        logger.info(f"OTA {ota.get_progress():>3}% - {ota.get_status()}")
        await asyncio.sleep(0.4)
    led.value(1)

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
        try:
            os.remove("ota_pending.flag")
        except:
            logger.warn("Could not remove ota_pending.flag after failed apply")

async def verify_ota_commit():
    if "ota_commit_pending.flag" not in os.listdir("/"):
        return
    logger.info("🔎 Verifying OTA commit...")
    ota = OTAUpdater(REPO_URL)
    for _ in range(12):
        try:
            if not await ota.check_for_update():
                logger.info("✅ OTA commit verified.")
                try:
                    os.remove("ota_commit_pending.flag")
                except Exception as e:
                    logger.warn(f"Could not remove ota_commit_pending.flag: {e}")
                return
        except Exception as e:
            logger.warn(f"Commit check failed: {e}")
        await asyncio.sleep(5)
    logger.error("❌ OTA commit verification failed. Rolling back...")
    await ota.rollback()

async def check_and_download_ota(led):
    updater = OTAUpdater(REPO_URL)
    while True:
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
                    progress_task = asyncio.create_task(show_progress(updater, led))
                    if await updater.download_update():
                        progress_task.cancel()
                        led.value(1)
                        with open("/ota_pending.flag", "w") as f:
                            f.write("ready")
                        for i in range(10, 0, -1):
                            print(f"Rebooting in {i} seconds... Press Ctrl+C to cancel.")
                            await asyncio.sleep(1)
                        machine.reset()
                    else:
                        progress_task.cancel()
                        led.value(0)
                        logger.error("❌ Download failed.")
            else:
                logger.warn("🚫 Not enough memory for OTA.")
        else:
            logger.info("✅ Firmware is up to date.")
        await asyncio.sleep(60)