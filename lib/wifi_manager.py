import network
import uasyncio as asyncio
import socket
import time
import urequests
import ntptime
from logger import Logger  # Import logger module

class WiFiManager:
    def __init__(self, ssid: str, password: str):
        self.ssid = ssid
        self.password = password
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.internet_available = False  # Internet status flag
        self.reconnect_attempts = 0  # Track failed reconnections
        self.ip_address = None  # Store connected IP address
        self.wifi_status = "Disconnected"  # Track Wi-Fi status
        self.internet_status = "Disconnected"  # Track Internet status
        self.connecting = False
        self.time_sync = "Pending"
        self.time_sync_in_progress = False
        self.last_ntp_attempt = 0  # utime.ticks_ms()

    async def connect(self):
        """Connect to Wi-Fi with error handling and guarded reconnection logic."""
        if self.connecting:
            Logger.debug("connect() already in progress. Skipping.")
            return

        self.connecting = True  # Guard flag ON
        try:
            if not self.wlan.isconnected():
                if not self.wlan.active():
                    Logger.debug("Activating WLAN interface...")
                    self.wlan.active(True)

                Logger.debug(f"Connecting to SSID: {self.ssid}...")
                self.wlan.connect(self.ssid, self.password)

                max_attempts = 10
                for attempt in range(max_attempts):
                    if self.wlan.isconnected():
                        await asyncio.sleep(2)  # Allow DHCP to settle
                        self.ip_address = self.wlan.ifconfig()[0]
                        self.wifi_status = "Connected"
                        Logger.info(f"Connected! IP: {self.ip_address}")
                        self.reconnect_attempts = 0
                        return
                    Logger.debug(f"Connection attempt {attempt + 1}/{max_attempts}...")
                    await asyncio.sleep(2)

                self.wifi_status = "Disconnected"
                Logger.error("Failed to connect after retries.")
        except OSError as e:
            Logger.error(f"Wi-Fi connection error: {e}")
        finally:
            self.connecting = False  # Guard flag OFF

    async def _http_probe(self, url):
        try:
            response = urequests.get(url, timeout=3)  # Still keep socket timeout
            response.close()
            return True
        except Exception as e:
            Logger.warn(f"HTTP probe failed: {e}")
            return False

    async def check_internet(self, online_lock):
        """ Fast-failing Internet check with full request timeout protection """
        if not self.wlan.isconnected():
            self.internet_available = False
            self.internet_status = "Disconnected"
            self.time_sync = "Pending"
            online_lock.clear()
            return

        success = False
        try:
            # Entire HTTP lifecycle limited to 4 seconds total
            success = await asyncio.wait_for(self._http_probe("http://clients3.google.com/generate_204"), timeout=4)
        except asyncio.TimeoutError:
            Logger.warn("Internet check hard timeout hit.")

        if success:
            if not self.internet_available:
                self.internet_available = True
                self.internet_status = "Connected"
                online_lock.set()

            if self.time_sync == "Pending" and not self.time_sync_in_progress:
                asyncio.create_task(self.safe_ntp_sync())
        else:
            if self.internet_available:
                Logger.error("Internet connection lost!")
            self.internet_available = False
            self.internet_status = "Disconnected"
            self.time_sync = "Pending"
            online_lock.clear()

    async def monitor_connection(self, online_lock):
        """ Continuously monitor Wi-Fi & Internet status, ensuring initial and recovery connection. """
        first_run = True  # Ensure initial connection attempt

        while True:
            self.wifi_status = "Connected" if self.wlan.isconnected() else "Disconnected"

            if self.wifi_status == "Connected":
                current_ip = self.wlan.ifconfig()[0]
                if current_ip and current_ip != "0.0.0.0":
                    self.ip_address = current_ip
                else:
                    Logger.warn("Connected to Wi-Fi but IP address not properly assigned.")
            else:
                self.ip_address = None
                online_lock.clear()

            # Initial connection or recovery attempt if disconnected
            if first_run or self.wifi_status == "Disconnected":
                if not self.connecting:
                    self.reconnect_attempts += 1
                    Logger.warn(f"Wi-Fi disconnected! Attempting reconnect ({self.reconnect_attempts})...")
                    await self.connect()
                first_run = False

            await self.check_internet(online_lock)
            await asyncio.sleep(5)

    def start(self,online_lock):
        """ Start Wi-Fi connection and monitoring """
        asyncio.create_task(self.monitor_connection(online_lock))

    def get_status(self):
        """ Ensure Wi-Fi & Internet status reflect reality correctly """
        if not self.wlan.isconnected():
            self.internet_status = "Disconnected"  # Prevent incorrect status overwrite
        return {"WiFi": self.wifi_status, "Internet": self.internet_status}

    def get_ip_address(self):
        """ Return stored IP only when Wi-Fi is connected """
        if self.wlan.isconnected():
            self.ip_address = self.wlan.ifconfig()[0]
            return self.ip_address
        return "Not connected"

    async def safe_ntp_sync(self):
        """Retryable time sync with flag tracking and delayed reattempts."""
        self.time_sync_in_progress = True
        attempt_count = 0
        max_attempts = 3

        while attempt_count < max_attempts and self.time_sync != "Synchronized":
            try:
                Logger.debug(f"NTP sync attempt {attempt_count + 1}")
                ntptime.settime()
                time.localtime(time.time() + 19800)
                self.time_sync = "Synchronized"
                Logger.info("System time synced successfully.")
                break
            except Exception as e:
                Logger.warn(f"NTP sync failed: {e}")
                attempt_count += 1
                await asyncio.sleep(10)  # Delay between retries

        if self.time_sync != "Synchronized":
            Logger.warn("NTP sync unsuccessful after retries.")
            self.time_sync = "Pending"  # Remains pending for future attempts

        self.time_sync_in_progress = False


if __name__ == "__main__":
    import uasyncio as asyncio
    #from wifi_manager import WiFiManager
    from logger import Logger  # Import logger module

    # Enable or disable debug logs
    Logger.DEBUG_MODE = True  # Set to True for debugging, False for production

    online_lock = asyncio.Event()
    online_lock.clear() #Disconnected at start
    
    wifi = WiFiManager(ssid="GHOSH_SAP", password="lifeline101")
    wifi.start(online_lock)

    async def main():
        while True:
            status = wifi.get_status()
            print(f"WiFi Status: {status['WiFi']}, Internet Status: {status['Internet']}")
            print(f"Current IP Address: {wifi.get_ip_address()}")
            await asyncio.sleep(10)  # Query status every 10 seconds

    asyncio.run(main())
