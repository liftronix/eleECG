# sysmon.py

import uos
import gc
import asyncio
import logger

# --- Configuration ---
BASELINE_IDLE_TICKS = 16683  # Measured 100% idle reference, Pico2W
MONITOR_INTERVAL = 5         # Seconds between samples
#BASELINE_IDLE_TICKS = 8970   # Your measured 100% idle reference, PicoW

# --- Internal State ---
_idle_counter = 0

# --- Idle Task ---
async def idle_task():
    global _idle_counter
    while True:
        _idle_counter += 1
        await asyncio.sleep_ms(0)

# --- CPU Utilization ---
def get_cpu_usage(idle_ticks: int) -> str:
    usage = max(0.0, (1 - idle_ticks / BASELINE_IDLE_TICKS)) * 100
    return f"🔥 CPU Active: {usage:.2f}%"

# --- Memory Monitor ---
def memory_usage(full: bool = False) -> str:
    gc.collect()
    free_mem = gc.mem_free()
    allocated_mem = gc.mem_alloc()
    total_mem = free_mem + allocated_mem
    percent_free = '{:.2f}%'.format(free_mem / total_mem * 100)
    if full:
        return f"🧠 Memory - Total:{total_mem} Free:{free_mem} ({percent_free})"
    return percent_free

# --- Flash Monitor ---
def flash_usage() -> str:
    stats = uos.statvfs('/')
    block_size, total_blocks, free_blocks = stats[0], stats[2], stats[3]
    total = block_size * total_blocks
    free = block_size * free_blocks
    used = total - free
    percent_used = '{:.2f}%'.format(used / total * 100)
    return f"💾 Flash - Total:{total} Used:{used} ({percent_used})"

# --- Resource Monitor Task ---
async def monitor_resources():
    global _idle_counter
    while True:
        snapshot = _idle_counter
        await asyncio.sleep(MONITOR_INTERVAL)
        ticks = _idle_counter - snapshot
        logger.debug(get_cpu_usage(ticks))
        logger.debug(memory_usage(full=True))
        logger.debug(flash_usage())
        logger.debug("—" * 40)