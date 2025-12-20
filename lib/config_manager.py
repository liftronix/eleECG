# config_manager.py
# Field-hardened configuration management with:
# - SD/flash/defaults fallback (fault tolerant)
# - Automatic SD healing and sync
# - Schema versioning and upgrade-on-boot
# - Firmware version awareness via version.txt
# - Optional OLED feedback for user transparency
# - Atomic writes to avoid corruption on power loss

import ujson
import os
from logger import Logger

# Example mapping: firmware version → required config schema version
FIRMWARE_SCHEMA_MAP = {
    "0.4.46": 2,   # Firmware 0.4.45 requires schema v2
    #"0.4.47": 3,   # Next firmware bumps schema to v3
    # Add more entries as firmware evolves
}

class ConfigManager:
    def __init__(self,
                 sd_path="/sd/config.json",
                 flash_path="/config.json",
                 version_path="/version.txt",
                 oled=None):
        """
        sd_path: Path to config on SD card (user-editable).
        flash_path: Shadow copy in internal flash (authoritative fallback).
        version_path: Firmware version file maintained by OTA tooling.
        oled: Optional OLED driver instance with .clear(), .text(), .show()
        """
        self.sd_path = sd_path
        self.flash_path = flash_path
        self.version_path = version_path
        self.oled = oled

        # Default schema (baseline). All new fields must be added here with sensible defaults.
        # Keys that users omit (e.g., in older configs) are merged in automatically at load.
        self.defaults = {
            "version": 1,  # Config schema version (not firmware version)
            "wifi": {
                "ssid": "default_ssid",
                "password": "default_pass"
            },
            "mqtt": {
                "host": "demo.thingsboard.io",
                "key": "",
                # Store numeric values as strings only if necessary; prefer integers for intervals.
                "publish_interval_sec": 5
            },
            "timezone": {
                "offset_sign": "+1",
                "offset_hours": 5,
                "offset_minutes": 30
            },
            "low_power": {
                "battery_time_mins": 20,
                "restore_debounce_sec": 30
            },
            "thresholds": {
                "temp_high": 50,
                "temp_low": 0,
                "humidity_high": 80,
                "humidity_low": 10,
                "noise_high": 1.00,
                "noise_low": 0.01
            }
        }

        # Example: defaults introduced in newer firmware versions.
        # Bump this when you add schema fields.
        self.latest_schema_version = 2

    # ------------- Public API -------------

    def load(self):
        """
        Load configuration with full resilience:
        - Try SD config → if missing/corrupt, fall back to flash → else defaults.
        - Upgrade schema to latest (merge new keys).
        - Compare firmware vs. schema; if firmware is newer, force upgrade.
        - Heal SD with the upgraded config and sync flash shadow copy.
        Always returns a valid config dict.
        """
        cfg, source = self._load_preferring_sd()
        self._oled_msg(self._status_msg_for_source(source))

        # Persist source for telemetry/diagnostics if useful downstream
        cfg["_meta"] = {
            "source": source,  # "SD" | "flash" | "defaults"
        }

        # Upgrade schema (adds new keys without overwriting user values)
        old_schema_version = cfg.get("version", 1)
        cfg = self._upgrade_schema(cfg)

        # If upgraded, warn and inform user via OLED
        if cfg.get("version", old_schema_version) > old_schema_version:
            Logger.warn(f"Old config detected (v{old_schema_version}), upgraded to v{cfg['version']}")
            self._oled_msg("⚠ Config upgraded")

        # Sync schema to firmware version (if firmware newer than config schema)
        fw_version = self._read_firmware_version()
        Logger.info(f"Firmware {fw_version}, Config schema {cfg.get('version')}")
        cfg = self._sync_schema_with_firmware(cfg, fw_version)

        # Write back to SD (healing/forwarding) and keep flash as authoritative
        self._persist_config(cfg)

        return cfg

    def sync(self):
        """
        Force a manual sync: if SD differs from flash, copy SD → flash.
        Useful if user updated SD in-field and you want to accept it explicitly.
        Note: load() already performs healing/upgrade and sync paths on boot.
        """
        sd_cfg = self._load_json(self.sd_path)
        flash_cfg = self._load_json(self.flash_path)
        if sd_cfg and (sd_cfg != flash_cfg):
            self._safe_write(self.flash_path, sd_cfg)
            Logger.info("Synced config.json from SD → flash")
        else:
            Logger.info("Config already up to date (SD == flash)")

    # ------------- Internal: Source selection -------------

    def _load_preferring_sd(self):
        """
        Try SD first. If missing/corrupt → use flash. If both fail → defaults.
        Heal SD if possible. Returns (cfg_dict, source_str).
        """
        cfg = self._load_json(self.sd_path)
        if cfg is not None:
            # Accept SD but do not trust it blindly; schema upgrade will fix it.
            Logger.info("Loaded config from SD")
            return cfg, "SD"

        Logger.warn("No valid config.json on SD, falling back...")
        self._oled_msg("⚠ No SD config")

        cfg = self._load_json(self.flash_path)
        if cfg is not None:
            Logger.info("Loaded config from flash shadow copy")
            # Heal SD with flash source if SD exists/mounts
            if self._path_parent_exists(self.sd_path):
                try:
                    self._safe_write(self.sd_path, cfg)
                    Logger.info("Healed SD config.json from flash")
                    self._oled_msg("✔ SD healed")
                except OSError:
                    Logger.warn("SD heal failed, SD path not writable")
            else:
                Logger.warn("SD path not present, continuing without SD")
                self._oled_msg("⚠ SD missing")
            return cfg, "flash"

        # Both SD and flash failed → use defaults
        Logger.warn("No config found on SD or flash; using defaults")
        self._oled_msg("⚠ Defaults in use")
        cfg = self._deepcopy(self.defaults)

        # Try writing defaults to SD and flash (best effort)
        self._best_effort_seed_storage(cfg)
        return cfg, "defaults"

    # ------------- Internal: Upgrade & version sync -------------

    def _upgrade_schema(self, cfg):
        """
        Merge latest defaults into user config.
        - Adds new keys introduced in newer schema versions.
        - Preserves user values if already present.
        """
        latest_defaults = self._latest_defaults()
        upgraded = self._merge_dicts(latest_defaults, cfg)
        # Do not blindly overwrite version here; let _sync_schema_with_firmware set it
        return upgraded

    def _sync_schema_with_firmware(self, cfg, fw_version):
        """
        Refined schema sync:
        - Look up required schema version for current firmware.
        - If config schema < required, upgrade once.
        - Avoid comparing patch numbers directly.
        """
        required_schema = FIRMWARE_SCHEMA_MAP.get(fw_version, self.latest_schema_version)
        current_schema = int(cfg.get("version", 1))

        if current_schema < required_schema:
            Logger.warn(f"Config schema {current_schema} < required {required_schema}, upgrading...")
            cfg = self._upgrade_schema(cfg)
            cfg["version"] = required_schema
        else:
            Logger.info(f"Config schema {current_schema} already satisfies firmware {fw_version}")

        return cfg

    # ------------- Internal: Persistence -------------

    def _persist_config(self, cfg):
        """
        Persist upgraded/validated config to both flash and SD (if available).
        - Flash shadow copy is the authoritative fallback.
        - SD gets healed/forwarded to the latest schema so user media is current.
        """
        # Write flash first (authoritative)
        try:
            self._safe_write(self.flash_path, cfg)
            Logger.info("Updated flash shadow copy")
        except OSError:
            Logger.error("Failed to update flash shadow copy")

        # Then write SD (best effort)
        if self._path_parent_exists(self.sd_path):
            try:
                self._safe_write(self.sd_path, cfg)
                Logger.info("Updated SD config.json to latest schema")
            except OSError:
                Logger.warn("Failed to update SD config.json (writable path?)")
        else:
            Logger.warn("SD path not present; skipping SD update")

    def _best_effort_seed_storage(self, cfg):
        """
        Attempt to seed both flash and SD with config. Used when neither had a valid file.
        """
        try:
            self._safe_write(self.flash_path, cfg)
            Logger.info("Seeded flash with defaults")
        except OSError:
            Logger.error("Failed to seed flash with defaults")

        if self._path_parent_exists(self.sd_path):
            try:
                self._safe_write(self.sd_path, cfg)
                Logger.info("Seeded SD with defaults")
            except OSError:
                Logger.warn("Failed to seed SD with defaults")

    # ------------- Helpers: IO & data ops -------------

    def _safe_write(self, path, data):
        """
        Atomic write pattern with pretty formatting for MicroPython:
        - Serialize config dictionary to JSON text using ujson (no indent support).
        - Add crude formatting: newlines after commas/braces for readability in Notepad.
        - Write to a temporary file first, then rename to target (atomic replace).
        """
        import ujson

        # Compact JSON string
        text = ujson.dumps(data)

        # Add simple pretty formatting for readability
        # Each key/value will appear on its own line
        text = text.replace(",", ",\n").replace("{", "{\n").replace("}", "\n}")

        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as f:
            f.write(text)
            # Closing flushes buffers in MicroPython

        # Atomically replace target file with temp file
        os.rename(tmp_path, path)

    def _load_json(self, path):
        try:
            with open(path) as f:
                return ujson.load(f)
        except OSError:
            return None
        except ValueError:
            Logger.warn(f"Config parse error (invalid JSON) at {path}")
            return None

    def _read_firmware_version(self):
        try:
            with open(self.version_path) as f:
                return f.read().strip()
        except OSError:
            Logger.warn("version.txt not found; defaulting to 0.0.0")
            return "0.0.0"

    def _merge_dicts(self, defaults, user):
        """
        Recursive merge:
        - For each key in defaults:
          - If missing in user, copy default.
          - If both are dicts, merge recursively.
          - If present in user and not a dict, keep user value.
        """
        # Ensure we don't mutate the defaults dictionary
        if not isinstance(user, dict):
            # If user is not a dict (corruption), start from defaults
            return self._deepcopy(defaults)

        for k, v in defaults.items():
            if k not in user:
                user[k] = self._deepcopy(v)
            elif isinstance(v, dict) and isinstance(user[k], dict):
                self._merge_dicts(v, user[k])
            # else: keep user-provided scalar/list as-is
        return user

    def _latest_defaults(self):
        """
        Return a copy of the latest defaults (include fields added by newer firmware).
        Example: add new keys here as firmware evolves.
        """
        latest = self._deepcopy(self.defaults)

        # Example: new config keys introduced post-OTA
        # - mqtt.tls_enabled (bool)
        # - mqtt.port (int)
        if "mqtt" not in latest:
            latest["mqtt"] = {}
        latest["mqtt"].setdefault("tls_enabled", False)
        latest["mqtt"].setdefault("port", 1883)

        # Bump schema version to the latest
        latest["version"] = self.latest_schema_version
        return latest

    def _path_parent_exists(self, path):
        """
        Check that the parent folder of `path` is present and listable.
        Helps decide whether SD is mounted.
        """
        try:
            parent = "/".join(path.split("/")[:-1]) or "."
            _ = os.listdir(parent)
            return True
        except:
            return False

    def _deepcopy(self, obj):
        """
        Simple deepcopy using JSON round-trip to avoid importing copy in MicroPython.
        Handles dicts/lists/scalars supported by JSON.
        """
        try:
            return ujson.loads(ujson.dumps(obj))
        except:
            # Fallback: return object as-is if not JSON-serializable
            return obj

    # ------------- Helpers: OLED UX -------------

    def _oled_msg(self, msg):
        """
        Show a short message on OLED if provided.
        Best effort; failures are logged but do not raise.
        """
        if not self.oled or not msg:
            return
        try:
            self.oled.clear()
            # Adjust positions for your display; these are placeholders.
            self.oled.text(msg, 0, 0)
            self.oled.show()
        except Exception as e:
            Logger.warn(f"OLED display failed: {e}")

    def _status_msg_for_source(self, source):
        """
        Small helper to decide the initial OLED message based on config source.
        """
        if source == "SD":
            return "✔ Config from SD"
        if source == "flash":
            return "✔ Config from flash"
        if source == "defaults":
            return "⚠ Defaults in use"
        return None

'''
# main.py
# Demonstrates boot-time config load, safe schema upgrade, and runtime usage.

from config_manager import ConfigManager
from logger import Logger

# Optional: your OLED driver instance, if available.
# from oled_driver import OLED
# oled = OLED(...)  # pass the correct pins/params
oled = None  # set to a real instance if you have one

def boot():
    # Initialize config manager with default paths; pass OLED if you want user-facing messages
    cm = ConfigManager(
        sd_path="/sd/config.json",
        flash_path="/config.json",
        version_path="/version.txt",
        oled=oled
    )

    # Load config (resilient): prefers SD, falls back to flash, else defaults; upgrades schema; syncs SD/flash
    cfg = cm.load()

    # Use config safely: all expected keys will be present after upgrade
    wifi_ssid = cfg["wifi"]["ssid"]
    wifi_pass = cfg["wifi"]["password"]

    mqtt_host = cfg["mqtt"]["host"]
    mqtt_key = cfg["mqtt"]["key"]
    mqtt_port = cfg["mqtt"]["port"]
    mqtt_tls  = cfg["mqtt"]["tls_enabled"]
    pub_interval = cfg["mqtt"]["publish_interval_sec"]

    # Log essential config values (avoid secrets in production logs if needed)
    Logger.info(f"WiFi SSID: {wifi_ssid}")
    Logger.info(f"MQTT host: {mqtt_host}:{mqtt_port} TLS={mqtt_tls}")
    Logger.info(f"Publish interval: {pub_interval}s")

    # Example runtime behavior:
    # - Attempt a manual sync if you allowed users to edit SD and want to accept those changes
    # cm.sync()

    # Continue with the rest of your initialization...
    # init_wifi(wifi_ssid, wifi_pass)
    # init_mqtt(mqtt_host, mqtt_port, tls=mqtt_tls, key=mqtt_key)
    # ...

if __name__ == "__main__":
    boot()
'''