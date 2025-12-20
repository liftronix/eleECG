import _thread
import utime

# -----------------------------
# Sensor data (thread-safe)
# -----------------------------

_sensor_data = {}    # {'mic': {payload}, 'mpu': {payload}, ...}
_sensor_seq = {}     # {'mic': 101, 'mpu': 56, ...}
_sensor_lock = _thread.allocate_lock()

def push_sensor_data(data: dict):
    """Store latest sensor payload and bump per-sensor sequence."""
    sensor = data.get('sensor')
    if not sensor:
        return  # Ignore if no sensor tag
    _sensor_lock.acquire()
    try:
        _sensor_seq[sensor] = _sensor_seq.get(sensor, 0) + 1
        _sensor_data[sensor] = data.copy()
    finally:
        _sensor_lock.release()

def get_sensor_snapshot():
    """Return a snapshot with shallow copies to avoid cross-thread mutation."""
    _sensor_lock.acquire()
    try:
        return {
            'seq': _sensor_seq.copy(),
            'payload': _sensor_data.copy()
        }
    finally:
        _sensor_lock.release()
