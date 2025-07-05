from machine import I2C
import utime

MPU_ADDR = 0x68

# Register addresses
PWR_MGMT_1 = 0x6B
ACCEL_XOUT_H = 0x3B
GYRO_XOUT_H = 0x43
TEMP_OUT_H = 0x41

class MPU6050:
    def __init__(self, i2c: I2C, addr=MPU_ADDR):
        self.i2c = i2c
        self.addr = addr
        self.init()

    def init(self):
        try:
            self.i2c.writeto_mem(self.addr, PWR_MGMT_1, b'\x00')  # Wake up
            utime.sleep_ms(100)
        except Exception as e:
            raise RuntimeError(f"MPU6050 init failed: {e}")

    def _read16(self, reg):
        raw = self.i2c.readfrom_mem(self.addr, reg, 2)
        val = (raw[0] << 8) | raw[1]
        return val - 65536 if val > 32767 else val

    def get_accel(self):
        return {
            'x': self._read16(ACCEL_XOUT_H) / 16384.0,
            'y': self._read16(ACCEL_XOUT_H + 2) / 16384.0,
            'z': self._read16(ACCEL_XOUT_H + 4) / 16384.0
        }

    def get_gyro(self):
        return {
            'x': self._read16(GYRO_XOUT_H) / 131.0,
            'y': self._read16(GYRO_XOUT_H + 2) / 131.0,
            'z': self._read16(GYRO_XOUT_H + 4) / 131.0
        }

    def get_temp(self):
        return self._read16(TEMP_OUT_H) / 340.0 + 36.53

if __name__ == "__main__":
    from machine import I2C, Pin
    #from mpu6050_minimal import MPU6050

    i2c = I2C(0, scl=Pin(1), sda=Pin(0))
    mpu = MPU6050(i2c)

    print("Accel:", mpu.get_accel())
    print("Gyro:", mpu.get_gyro())
    print("Temp:", mpu.get_temp())
