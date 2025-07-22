from machine import ADC, Pin, I2C, Timer
from mpu6050_minimal import MPU6050
from shared_state import push_sensor_data
import utime, math, micropython
import random
from time import ticks_ms, ticks_diff
import logger


micropython.alloc_emergency_exception_buf(100)

# --- Timers ---
mic_timer = None
mpu_timer = None
mpu_temp_timer = None
door_timer = None
power_timer = None

# --- MIC Setup ---
AUDIO_PIN = 26
SAMPLE_COUNT = 512
SAMPLE_DELAY_US = 50  # ~20 kHz sampling
DB_REF = 0.707        # Reference voltage for dB scaling
PTP_THRESHOLD = 0.05  # Minimum peak-to-peak voltage to flag activity

adc = ADC(Pin(AUDIO_PIN))
conv = 3.3 / 65535

def compute_metrics(samples):
    mean = sum(samples) / len(samples)
    centered = [(v - mean) for v in samples]

    rms = math.sqrt(sum(v**2 for v in centered) / len(centered))
    db = 20 * math.log10(rms / DB_REF) if rms > 0 else -float('inf')
    ptp = max(samples) - min(samples)

    return {
        'rms': rms,
        'db': db,
        'ptp': ptp,
        'mean': mean
    }

def mic_cb_stub(timer):
    micropython.schedule(mic_cb_scheduled, 0)

def mic_cb_scheduled(_):
    try:
        samples = []
        for _ in range(SAMPLE_COUNT):
            samples.append(adc.read_u16() * conv)
            utime.sleep_us(SAMPLE_DELAY_US)  # ~20kHz sampling

        metrics = compute_metrics(samples)
        push_sensor_data({
            'sensor': 'mic',
            'disp_data':metrics['ptp'],
            'rms': metrics['rms'],
            'db': metrics['db'],
            'P2P': metrics['ptp']
        })
    except Exception as e:
        push_sensor_data({'sensor': 'mic', 'error': str(e)})

# --- MPU6050 Setup ---
try:
    i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400_000)
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

# --- MPU6050 Temperature Setup ---
def mpu_temp_cb_stub(timer):
    micropython.schedule(mpu_temp_cb_scheduled, 0)

def mpu_temp_cb_scheduled(_):
    if not mpu: return
    try:
        temperature = mpu.get_temp()
        humidity = random.randint(60, 75)
        
        push_sensor_data({
            'sensor': 'mpu_temp',
            'disp_data': temperature,
            'temp': temperature
        })
        push_sensor_data({
            'sensor': 'humidity',
            'disp_data': humidity,
            'humid': humidity
        })

    except Exception as e:
        push_sensor_data({'sensor': 'mpu_temp', 'error': str(e)})

# --- DOOR Sensor Setup ---
# Initialize GPIO 0 and GPIO 1 as inputs
gpio0 = Pin(0, Pin.IN)
gpio1 = Pin(1, Pin.IN)

def door_cb_stub(timer):
    micropython.schedule(door_cb_scheduled, 0)
    
def door_cb_scheduled(_):
    try:
        d_open = gpio0.value()
        d_close = gpio1.value()
        #print("GPIO 0:", state0, " | GPIO 1:", state1)
        
        if(not d_open):
            push_sensor_data({'sensor':'door','disp_data':'OPEN'})
        elif(not d_close):
            push_sensor_data({'sensor':'door','disp_data':'CLOSED'})
        else:
            push_sensor_data({'sensor':'door','disp_data':'NO NC'})
        
    except Exception as e:
        push_sensor_data({'sensor': 'door', 'error': str(e)})


# --- Power Setup ---
adc = ADC(Pin(28)) # ADC for battery voltage on GPIO28 (ADC2)
charger_pin = Pin(10, Pin.IN)# Charger indication input on GPIO10
# Voltage reference and resistor values
VREF = 3.3  # Reference voltage for ADC
R1 = 10000   # Resistor to battery positive
R2 = 3600   # Resistor to GND
# Divider correction factor
voltage_divider_factor = (R1 + R2) / R2

# --- Rolling Average Setup ---
WINDOW_SIZE = 10
voltage_samples = []

def get_smoothed_voltage():
    voltage = read_battery_voltage()
    # Maintain a fixed-size buffer
    voltage_samples.append(voltage)
    if len(voltage_samples) > WINDOW_SIZE:
        voltage_samples.pop(0)
    
    avg_voltage = sum(voltage_samples) / len(voltage_samples)
    return round(avg_voltage, 2)

def read_battery_voltage():
    raw = adc.read_u16()
    voltage_at_pin = (raw / 65535) * VREF
    actual_voltage = voltage_at_pin * voltage_divider_factor
    return round(actual_voltage, 2)

def read_charger_status():
    return "OFF" if charger_pin.value() else "ON"

# GPIO2 controls the MOSFET
power_gate_pin = Pin(2, Pin.OUT)

def enter_low_power_mode():
    power_gate_pin.value(0)  # Turn off peripherals
    logger.warn('Entering Low Power Mode')
    #push_sensor_data({'event': 'Low Power Mode Activated'})
    # Optional: reduce timer frequency if your callback is very frequent

def exit_low_power_mode():
    power_gate_pin.value(1)  # Turn peripherals back on
    logger.warn('Exiting Low Power Mode')
    #push_sensor_data({'event': 'Exited Low Power Mode'})
    
# State tracking
power_state = {
    'mains': True,
    'low_power_mode': False,
    'mains_lost_at': None,
    'mains_restored_at': None
}

POWER_RESTORE_DEBOUNCE_MS = 30 * 1000  # 10 seconds
LOW_POWER_DELAY_MS = 20 * 60 * 1000  # 20 minutes
TICKS_AT_RESET = 15000

def power_cb_stub(timer):
    micropython.schedule(power_cb_scheduled, 0)

def power_cb_scheduled(_):
    try:
        vbat = get_smoothed_voltage()
        mains_on = read_charger_status() == 'ON'
        now = ticks_ms()

        # Track mains OFF time
        if not mains_on:
            if power_state['mains']:
                power_state['mains_lost_at'] = now
                logger.warn(f"Mains Power: CUTOFF : {now}")
                if(now < TICKS_AT_RESET):
                    enter_low_power_mode()
                    power_state['low_power_mode'] = True
            power_state['mains_restored_at'] = None  # Cancel recovery debounce
        else:
            if not power_state['mains']:
                power_state['mains_restored_at'] = now  # Just restored
                logger.warn(f"Mains Power: RESTORED : {now}")

        power_state['mains'] = mains_on

        # Enter low power mode
        if not mains_on and power_state['mains_lost_at']:
            elapsed = ticks_diff(now, power_state['mains_lost_at'])
            if (elapsed > LOW_POWER_DELAY_MS) and not power_state['low_power_mode']:
                enter_low_power_mode()
                power_state['low_power_mode'] = True

        # Debounced recovery
        if mains_on and power_state['low_power_mode'] and power_state['mains_restored_at']:
            restore_elapsed = ticks_diff(now, power_state['mains_restored_at'])
            if restore_elapsed > POWER_RESTORE_DEBOUNCE_MS:
                exit_low_power_mode()
                power_state['low_power_mode'] = False
                power_state['mains_restored_at'] = None  # Clear timestamp after recovery

        # Telemetry
        push_sensor_data({'sensor': 'batt', 'disp_data': f"{vbat}V", 'V_Batt': vbat})
        push_sensor_data({'sensor': 'mains', 'disp_data': 'ON' if mains_on else 'OFF', 'AC_Power': 'ON' if mains_on else 'OFF'})

    except Exception as e:
        push_sensor_data({'sensor': 'Mains', 'error': str(e)})



# --- Core 1 Entry Point ---
def core1_main():
    global mic_timer, mpu_timer, mpu_temp_timer, door_timer

    mic_timer = Timer()
    mic_timer.init(freq=1, mode=Timer.PERIODIC, callback=mic_cb_stub)

    if mpu:
        mpu_timer = Timer()
        mpu_timer.init(freq=1, mode=Timer.PERIODIC, callback=mpu_cb_stub)
    
    if mpu:
        mpu_temp_timer = Timer()
        mpu_temp_timer.init(freq=1, mode=Timer.PERIODIC, callback=mpu_temp_cb_stub)
        
    door_timer = Timer()
    door_timer.init(freq=1, mode=Timer.PERIODIC, callback=door_cb_stub)
    
    power_timer = Timer()
    power_timer.init(freq=1, mode=Timer.PERIODIC, callback=power_cb_stub)
    
    while True:
        utime.sleep(1)

def stop_core1():
    if mic_timer:
        mic_timer.deinit()
    if mpu_timer:
        mpu_timer.deinit()
    if mpu_temp_timer:
        mpu_temp_timer.deinit()
    if door_timer:
        door_timer.deinit()
    if power_timer:
        power_timer.deinit()
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