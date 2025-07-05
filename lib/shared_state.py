import _thread

_sensor_data = {}          # {'mic': {payload}, 'mpu': {payload}, ...}
_sensor_seq = {}           # {'mic': 101, 'mpu': 56, ...}
_lock = _thread.allocate_lock()

def push_sensor_data(data: dict):
    global _sensor_data, _sensor_seq
    sensor = data.get('sensor')
    if not sensor:
        return  # Ignore if no sensor tag

    with _lock:
        _sensor_seq[sensor] = _sensor_seq.get(sensor, 0) + 1
        _sensor_data[sensor] = data.copy()

def get_sensor_snapshot():
    with _lock:
        # Compose full snapshot
        snapshot = {
            'seq': _sensor_seq.copy(),
            'payload': _sensor_data.copy()
        }
        return snapshot