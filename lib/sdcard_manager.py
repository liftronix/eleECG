import machine
import os
import sdcard
import uasyncio as asyncio
from logger import Logger


class SDCardManager:
    def __init__(self, spi_id=0, cs_pin=17, sck=18, mosi=19, miso=16,
                 cd_pin=None, mount_point="/sd", baudrate=1_000_000,
                 debounce_ms=300):
        self.mount_point = mount_point
        self.cs = machine.Pin(cs_pin, machine.Pin.OUT)
        self.cd_pin = machine.Pin(cd_pin, machine.Pin.IN, machine.Pin.PULL_UP) if cd_pin is not None else None
        self.debounce_ms = debounce_ms

        self.spi = machine.SPI(
            spi_id,
            baudrate=baudrate,
            polarity=0,
            phase=0,
            bits=8,
            firstbit=machine.SPI.MSB,
            sck=machine.Pin(sck),
            mosi=machine.Pin(mosi),
            miso=machine.Pin(miso)
        )

        self.sd = None
        self.vfs = None
        self.mounted = False
        self._last_state = self.is_present()

    def is_present(self):
        if self.cd_pin:
            return self.cd_pin.value() == 0  # Active low card detect
        else:
            # No hardware CD pin—fallback based on mount state
            return self._can_access_mount()

    def _can_access_mount(self):
        try:
            os.listdir(self.mount_point)
            return True
        except:
            return False

    async def mount(self):
        if self.mounted:
            Logger.info("SD already mounted.")
            return
        try:
            self.sd = sdcard.SDCard(self.spi, self.cs)
            self.vfs = os.VfsFat(self.sd)
            os.mount(self.vfs, self.mount_point)
            self.mounted = True
            Logger.info("SD mounted at {}".format(self.mount_point))
        except Exception as e:
            Logger.error("Mount failed: {}".format(e))

    async def unmount(self):
        if not self.mounted:
            return
        try:
            os.umount(self.mount_point)
            self.mounted = False
            Logger.info("SD safely unmounted.")
        except Exception as e:
            Logger.error("Unmount failed: {}".format(e))

    def get_free_space_mb(self):
        try:
            s = os.statvfs(self.mount_point)
            return (s[0] * s[3]) / (1024 * 1024)
        except:
            return 0

    def list_files(self, path=""):
        try:
            return os.listdir(self._full_path(path))
        except:
            return []

    def write_file(self, filename, data, append=True, safe=False):
        mode = "a" if append else "w"
        path = self._full_path(filename)
        try:
            if safe:
                temp_path = path + ".tmp"
                with open(temp_path, mode) as f:
                    f.write(data)
                os.rename(temp_path, path)
                Logger.debug("Safely wrote: {}".format(path))
            else:
                with open(path, mode) as f:
                    f.write(data)
                Logger.debug("Wrote: {}".format(path))
        except Exception as e:
            Logger.error("Write failed for {}: {}".format(filename, e))

    def is_dir(self, path):
        try:
            return os.stat(self._full_path(path))[0] & 0x4000 == 0x4000
        except:
            return False

    def _full_path(self, path):
        return "{}/{}".format(self.mount_point.rstrip("/"), path.lstrip("/"))

    async def auto_manage(self, poll_interval_ms=1000):
        while True:
            if not self.mounted:
                try:
                    await self.mount()
                    Logger.info("Card inserted.")
                except:
                    pass
            else:
                if not self._can_access_mount():
                    Logger.warn("Card removed unexpectedly.")
                    await self.unmount()
            await asyncio.sleep_ms(poll_interval_ms)

'''
import machine, os, sdcard
spi = machine.SPI(0, sck=machine.Pin(18), mosi=machine.Pin(19), miso=machine.Pin(16))
cs = machine.Pin(17, machine.Pin.OUT)
sd = sdcard.SDCard(spi, cs)
os.mount(os.VfsFat(sd), "/sd")
print(os.listdir("/sd"))
'''