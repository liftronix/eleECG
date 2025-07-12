from machine import ADC, Pin, I2C, Timer
from mpu6050_minimal import MPU6050
from shared_state import push_sensor_data
import utime, math, micropython

micropython.alloc_emergency_exception_buf(100)

# --- Timers ---
mic_timer = None
mpu_timer = None

# --- MIC Setup ---
adc = ADC(Pin(26))
conv = 3.3 / 65535

def compute_rms_db(samples):
    rms = math.sqrt(sum(v**2 for v in samples) / len(samples))
    db = 20 * math.log10(rms / 0.707) if rms > 0 else -float('inf')
    return rms, db

def mic_cb_stub(timer):
    micropython.schedule(mic_cb_scheduled, 0)

def mic_cb_scheduled(_):
    try:
        samples = []
        for _ in range(512):
            samples.append(adc.read_u16() * conv)
            utime.sleep_us(50)  # ~20kHz sampling

        rms, db = compute_rms_db(samples)
        push_sensor_data({
            'sensor': 'mic',
            'disp_data':db,
            'rms': rms,
            'db': db
        })
    except Exception as e:
        push_sensor_data({'sensor': 'mic', 'error': str(e)})

# --- MPU6050 Setup ---
try:
    i2c = I2C(0, scl=Pin(15), sda=Pin(14), freq=400_000)
    mpu = MPU6050(i2c)
except Exception as e:
    mpu = None
    push_sensor_data({'sensor': 'mpu', 'error': f'Init failed: {e}'})

def mpu_cb_stub(timer):
    micropython.schedule(mpu_cb_scheduled, 0)

def mpu_cb_scheduled(_):
    if not mpu: return
    try:
        accel_samples = []
        for _ in range(128):
            accel_samples.append(mpu.get_accel())
            utime.sleep_ms(1)

        # RMS magnitude
        rms_mag = math.sqrt(sum(
            a['x']**2 + a['y']**2 + a['z']**2 for a in accel_samples
        ) / len(accel_samples))

        # Peak-to-peak Z
        z_vals = [a['z'] for a in accel_samples]
        peak_z = max(z_vals) - min(z_vals)

        # Vibration Index
        vib_index = rms_mag * peak_z

        push_sensor_data({
            'sensor': 'mpu',
            'disp_data': vib_index,
            'vib_index': vib_index,
            'rms_mag': rms_mag,
            'peak_z': peak_z
        })

    except Exception as e:
        push_sensor_data({'sensor': 'mpu', 'error': str(e)})

# --- Core 1 Entry Point ---
def core1_main():
    global mic_timer, mpu_timer

    mic_timer = Timer()
    mic_timer.init(freq=1, mode=Timer.PERIODIC, callback=mic_cb_stub)

    if mpu:
        mpu_timer = Timer()
        mpu_timer.init(freq=1, mode=Timer.PERIODIC, callback=mpu_cb_stub)

    while True:
        utime.sleep(1)

def stop_core1():
    if mic_timer:
        mic_timer.deinit()
    if mpu_timer:
        mpu_timer.deinit()
    print("🛑 Core 1 timers stopped.")
    
'''
import _thread, utime
from core1_manager import core1_main, stop_core1
from shared_state import get_sensor_data

_thread.start_new_thread(core1_main, ())

last_seq = -1

try:
    while True:
        snapshot = get_sensor_data()
        if snapshot and snapshot['seq'] != last_seq:
            last_seq = snapshot['seq']
            print(f"New Sample [{last_seq}] →", snapshot['payload'])
        utime.sleep_ms(100)

except KeyboardInterrupt:
    print("🔻 Ctrl+C detected — stopping timers…")
    stop_core1()
    utime.sleep(1)
'''