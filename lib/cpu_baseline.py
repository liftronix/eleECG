import uasyncio as asyncio

# Configuration
BASELINE_DURATION = 5  # duration (in seconds) for idle tick profiling

# Idle tick counter
idle_counter = 0

async def idle_task():
    global idle_counter
    while True:
        idle_counter += 1
        await asyncio.sleep_ms(0)

async def main():
    global idle_counter

    print(f"\n📡 Starting idle baseline profiling for {BASELINE_DURATION} seconds...\n")

    # Launch only the idle task
    asyncio.create_task(idle_task())

    # Clear counter and sleep
    idle_counter = 0
    await asyncio.sleep(BASELINE_DURATION)

    # Print result
    print("✅ Baseline complete.")
    print(f"🧮 Idle ticks recorded: {idle_counter}")
    print(f"📏 Duration: {BASELINE_DURATION} sec")
    print(f"📌 Suggested baseline value: {idle_counter} ticks\n")
    print("💡 Use this value as your reference for 100% idle when integrating CPU monitoring.\n")

asyncio.run(main())