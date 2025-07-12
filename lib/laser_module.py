import uasyncio as asyncio
import utime
from machine import UART, Pin
from logger import debug, info, warn, error

class LaserModule:
    def __init__(self, uart_id=0, baudrate=115200, tx_pin=12, rx_pin=13, pwr_pin=11):
        """
        Initialize laser module with UART and power pin.
        """
        self.uart = UART(uart_id, baudrate=baudrate, stop=1, tx=Pin(tx_pin), rx=Pin(rx_pin))
        self.pwr = Pin(pwr_pin, Pin.OUT)
        self.buffer = bytearray()
        self.timeout_ms = 700
        self.seq = {}
        self.payload = {}

    async def power_on(self) -> bool:
        """Power ON the laser module and send initialization command."""
        try:
            info("Laser: Powering ON")
            self.pwr.value(1)
            await asyncio.sleep_ms(500)
            await self._send_packet(b'\x01\xBE\x00\x01\x00\x01', b'\xC1')  # Enable laser
            return True
        except Exception as e:
            error(f"Laser: Power ON failed — {e}")
            return False

    async def power_off(self) -> bool:
        """Disable laser and set power pin LOW."""
        try:
            info("Laser: Powering OFF")
            await self._send_packet(b'\x01\xBE\x00\x01\x00\x00', b'\xC0')  # Disable laser
            await asyncio.sleep_ms(100)
            self.pwr.value(0)
            return True
        except Exception as e:
            error(f"Laser: Power OFF failed — {e}")
            return False

    async def _send_packet(self, payload: bytes, checksum_byte: bytes):
        """Construct and transmit UART packet."""
        packet = b'\xAA\x00' + payload + checksum_byte
        self.uart.write(packet)
        await asyncio.sleep_ms(20)

    async def _read_uart_response(self) -> bytes:
        """Read UART response with timeout and extract valid frame."""
        self.buffer = bytearray()
        start = utime.ticks_ms()

        while utime.ticks_diff(utime.ticks_ms(), start) < self.timeout_ms:
            if self.uart.any():
                self.buffer += self.uart.read(1)
            await asyncio.sleep_ms(2)

        buf = bytes(self.buffer)
        for i in range(len(buf) - 12):
            if buf[i] == 0xAA:
                frame = buf[i:i+13]
                if len(frame) == 13:
                    return frame

        warn(f"Laser: No valid frame in response — {buf}")
        return b''

    async def get_status(self) -> bytes:
        """Request status from laser module."""
        try:
            await self._send_packet(b'\x80\x00\x00', b'\x80')
            response = await self._read_uart_response()
            debug(f"Laser: Status response — {response}")
            return response
        except Exception as e:
            error(f"Laser: Status query failed — {e}")
            return b''

    async def measure(self, mode: str = "fast") -> int:
        """Trigger a distance measurement and return result in mm."""
        try:
            if mode == "auto":
                payload = b'\x00\x20\x00\x01\x00\x00'
                checksum = b'\x21'
                delay_ms = 600
            else:
                payload = b'\x00\x20\x00\x01\x00\x02'
                checksum = b'\x23'
                delay_ms = 600

            await self._send_packet(payload, checksum)
            await asyncio.sleep_ms(delay_ms)
            response = await self._read_uart_response()

            if response and len(response) == 13:
                distance = (response[6]<<24)|(response[7]<<16)|(response[8]<<8)|(response[9])
                info(f"Laser: Measured distance — {distance} mm")
                return distance
            else:
                warn(f"Laser: Invalid response — {response}")
                return -1
        except Exception as e:
            error(f"Laser: Measurement error — {e}")
            return -1

    async def measure_and_log(self, tag="laser", mode="fast"):
        """
        Performs measurement, logs result, updates sequence, and stores structured data.
        Returns snapshot containing seq + payload.
        """
        distance = await self.measure(mode)
        if distance >= 0:
            self.seq[tag] = self.seq.get(tag, -1) + 1
            self.payload = {tag: distance}
            entry = f"[{tag}] Seq={self.seq[tag]} → {distance}"
            debug(entry)
        return self.get_latest_snapshot()

    def get_latest_snapshot(self) -> dict:
        """
        Provides latest sensor output in standard format: {"seq": {}, "payload": {}}
        """
        return {
            "seq": self.seq.copy(),
            "payload": self.payload.copy()
        }

# 🧪 Optional standalone test
async def main():
    laser = LaserModule()

    if not await laser.power_on():
        error("Laser: Init failed")
        return

    await laser.get_status()

    try:
        while True:
            snapshot = await laser.measure_and_log(tag="laser")
            print("Snapshot:", snapshot)
            await asyncio.sleep_ms(500)
    except KeyboardInterrupt:
        warn("Laser: Shutdown")
        await laser.power_off()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        error(f"Laser: Fatal error — {e}")
