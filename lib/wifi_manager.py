import network
import uasyncio as asyncio
import socket
import time
import urequests
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

    async def connect(self):
        """ Connect to Wi-Fi with error handling and reconnection logic """
        if not self.wlan.isconnected():
            try:
                if not self.wlan.active():
                    Logger.debug("Activating WLAN interface...")
                    self.wlan.active(True)

                Logger.debug(f"Connecting to {self.ssid}...")
                self.wlan.connect(self.ssid, self.password)

                max_attempts = 10
                for attempt in range(max_attempts):
                    if self.wlan.isconnected():
                        await asyncio.sleep(2)  # Give time for IP assignment
                        self.ip_address = self.wlan.ifconfig()[0]
                        self.wifi_status = "Connected"
                        Logger.info(f"Connected! IP: {self.ip_address}")
                        self.reconnect_attempts = 0  # Reset counter after successful connection
                        return
                    await asyncio.sleep(2)

                self.wifi_status = "Disconnected"
                Logger.error("Failed to connect!")

            except OSError as e:
                Logger.error(f"Wi-Fi connection error: {e}")

    async def check_internet(self):
        """ Check Internet availability with retry logic """
        if not self.wlan.isconnected():
            self.internet_available = False
            self.internet_status = "Disconnected"
            return  # Skip check if Wi-Fi is disconnected

        retry_count = 3
        for _ in range(retry_count):
            try:
                response = urequests.get("http://clients3.google.com/generate_204", timeout=3)
                response.close()
                if not self.internet_available:
                    self.internet_available = True
                    self.internet_status = "Connected"
                return
            except Exception as e:
                Logger.warn(f"Internet check failed: {e}")
                await asyncio.sleep(2)  # Short delay before retry

        if self.internet_available:  # Only log change if status was previously connected
            self.internet_available = False
            self.internet_status = "Disconnected"
            Logger.error("Internet connection lost!")

    async def monitor_connection(self):
        """ Continuously check Wi-Fi & Internet status with forced refresh """
        while True:
            self.wifi_status = "Connected" if self.wlan.isconnected() else "Disconnected"
            
            if self.wifi_status == "Connected":
                self.ip_address = self.wlan.ifconfig()[0]

            if self.wifi_status == "Disconnected":
                self.reconnect_attempts += 1
                Logger.warn(f"Wi-Fi disconnected! Attempting reconnect ({self.reconnect_attempts})...")
                await self.connect()
            
            await self.check_internet()
            await asyncio.sleep(5)

    def start(self):
        """ Start Wi-Fi connection and monitoring """
        asyncio.create_task(self.connect())
        asyncio.create_task(self.monitor_connection())

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


if __name__ == "__main__":
    import uasyncio as asyncio
    #from wifi_manager import WiFiManager
    from logger import Logger  # Import logger module

    # Enable or disable debug logs
    Logger.DEBUG_MODE = False  # Set to True for debugging, False for production


    wifi = WiFiManager(ssid="GHOSH_SAP", password="lifeline101")
    wifi.start()

    async def main():
        while True:
            status = wifi.get_status()
            print(f"WiFi Status: {status['WiFi']}, Internet Status: {status['Internet']}")
            print(f"Current IP Address: {wifi.get_ip_address()}")
            await asyncio.sleep(10)  # Query status every 10 seconds

    asyncio.run(main())
