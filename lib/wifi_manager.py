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

    async def check_internet(self, online_lock):
        """ Check Internet availability with retry logic """
        if not self.wlan.isconnected():
            self.internet_available = False
            self.internet_status = "Disconnected"
            self.time_sync = "Pending"
            online_lock.clear()
            return  # Skip check if Wi-Fi is disconnected

        retry_count = 3
        for _ in range(retry_count):
            try:
                response = urequests.get("http://clients3.google.com/generate_204", timeout=3)
                response.close()
                if not self.internet_available:
                    self.internet_available = True
                    self.internet_status = "Connected"
                    online_lock.set()
                    if self.time_sync == "Pending":
                        asyncio.create_task(self.safe_ntp_sync())
                return
            except Exception as e:
                Logger.warn(f"Internet check failed: {e}")
                await asyncio.sleep(2)  # Short delay before retry

        if self.internet_available:  # Only log change if status was previously connected
            self.internet_available = False
            self.internet_status = "Disconnected"
            self.time_sync = "Pending"
            online_lock.clear()
            Logger.error("Internet connection lost!")

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
        """Attempt NTP sync with timeout protection."""
        try:
            await asyncio.wait_for(asyncio.create_task(self._ntp_wrapper()), timeout=6)
            self.time_sync = "Synchronized"
            Logger.info("System time synced.")
        except asyncio.TimeoutError:
            Logger.warn("NTP sync timed out.")
        except Exception as e:
            Logger.warn(f"NTP sync failed: {e}")
            
    async def _ntp_wrapper(self):
        ntptime.settime()
        time.localtime(time.time() + 19800)  # IST offset


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
