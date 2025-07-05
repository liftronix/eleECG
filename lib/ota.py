import uasyncio as asyncio
import urequests as requests
import os
import json
import hashlib
import binascii
import logger

class OTAUpdater:
    def __init__(self, repo_url, version_file="/version.txt", ota_dir="/update", backup_dir="/backup"):
        self.repo_url = repo_url.rstrip("/")
        self.manifest_url = f"{self.repo_url}/manifest.json"
        self.version_file = version_file
        self.ota_dir = ota_dir
        self.backup_dir = backup_dir
        self.manifest = {}
        self.files = []
        self.hashes = {}
        self.sizes = {}
        self.remote_version = ""
        self.progress = 0
        self.current_file = ""
        #Files to be excluded during OTA process
        self.user_excluded = {
            "config.json",
            "output_info.txt"
        }
    
    #--------------------------------------------------------------------------#
    def get_progress(self):
        return self.progress
    
    #--------------------------------------------------------------------------#
    def get_status(self):
        return f"{self.current_file} ({self.progress}%)"
    
    #--------------------------------------------------------------------------#
    async def _get_local_version(self):
        try:
            with open(self.version_file, "r") as f:
                return f.read().strip()
        except:
            return "0.0.0"
    
    #--------------------------------------------------------------------------#
    async def _ensure_dirs(self, path):
        parts = path.split("/")[:-1]
        current = ""
        for p in parts:
            current = f"{current}/{p}" if current else f"/{p}"
            try:
                os.mkdir(current)
                logger.debug(f"Created directory: {current}")
            except:
                pass
    
    #--------------------------------------------------------------------------#
    def _should_normalize(self, file_path):
        return file_path.endswith((".py", ".txt", ".json", ".md"))

    #--------------------------------------------------------------------------#
    def _sha256(self, path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                h.update(chunk)
        return binascii.hexlify(h.digest()).decode()
    
    #--------------------------------------------------------------------------#
    async def check_for_update(self):
        try:
            r = requests.get(self.manifest_url)
            self.manifest = r.json()
            self.remote_version = self.manifest.get("version", "")
            files_meta = self.manifest.get("files", {})
            self.hashes = {k: v["sha256"] for k, v in files_meta.items()}
            self.sizes = {k: v["size"] for k, v in files_meta.items()}
            self.files = list(self.hashes.keys())
            local = await self._get_local_version()
            logger.info(f"OTA → Local: {local} | Remote: {self.remote_version}")
            return self.remote_version and self.remote_version != local
        except Exception as e:
            logger.error(f"OTA: Failed to fetch manifest: {e}")
            return False
    
    #--------------------------------------------------------------------------#
    async def download_update(self):
        try:
            os.mkdir(self.ota_dir)
            logger.info(f"Created OTA directory: {self.ota_dir}")
        except:
            logger.debug(f"OTA directory already exists: {self.ota_dir}")

        total = len(self.files)
        for i, file in enumerate(self.files):
            url = f"{self.repo_url}/{file}"
            dest = f"{self.ota_dir}/{file}"
            await self._ensure_dirs(dest)
            self.current_file = file
            try:
                logger.info(f"Downloading: {file} → {url}")
                r = requests.get(url)
                content = r.content
                if self._should_normalize(file):
                    content = content.replace(b"\r\n", b"\n")
                    logger.debug(f"Normalized line endings for {file}")
                with open(dest, "wb") as f:
                    f.write(content)
                actual_hash = self._sha256(dest)
                expected_hash = self.hashes[file]
                if actual_hash != expected_hash:
                    logger.error(f"Hash mismatch: {file}")
                    return False
                logger.info(f"Downloaded {file} ✓")
                self.progress = int(((i + 1) / total) * 100)
                await asyncio.sleep_ms(10)
            except Exception as e:
                logger.error(f"Download failed: {file}: {e}")
                return False

        try:
            with open(f"{self.ota_dir}/manifest.json", "w") as f:
                json.dump(self.manifest, f)
            logger.debug("Saved manifest.json to OTA directory")
        except Exception as e:
            logger.error(f"Failed to save manifest.json: {e}")
            return False

        return True
    
    #--------------------------------------------------------------------------#
    async def apply_update(self):
        try:
            with open(f"{self.ota_dir}/manifest.json") as f:
                self.manifest = json.load(f)
            self.remote_version = self.manifest.get("version", "")
            files_meta = self.manifest.get("files", {})
            self.hashes = {k: v["sha256"] for k, v in files_meta.items()}
            self.sizes = {k: v["size"] for k, v in files_meta.items()}
            self.files = list(self.hashes.keys())
            if not self.remote_version:
                logger.error(f"OTA: Manifest missing version field → {self.manifest}")
                return False
        except Exception as e:
            logger.error(f"OTA: Failed to load manifest during apply: {e}")
            return False

        try:
            os.mkdir(self.backup_dir)
            logger.info(f"Created backup directory: {self.backup_dir}")
        except:
            logger.debug(f"Backup directory already exists: {self.backup_dir}")

        for f in self.files:
            if f in self.user_excluded:
                logger.info(f"⚠️ Skipping OTA apply for user-preserved file: {f}")
                continue
            src = f"/{f}"
            bkp = f"{self.backup_dir}/{f}"
            new = f"{self.ota_dir}/{f}"
            await self._ensure_dirs(bkp)
            try:
                os.stat(src)
                with open(src, "rb") as r, open(bkp, "wb") as w:
                    w.write(r.read())
                logger.debug(f"Backed up: {f}")
            except OSError:
                logger.warn(f"Source file missing, skipping backup: {src}")
            except Exception as e:
                logger.warn(f"Could not backup {f}: {e}")
            try:
                await self._ensure_dirs(src)
                with open(new, "rb") as r, open(src, "wb") as w:
                    w.write(r.read())
                logger.info(f"Applied: {f}")
            except Exception as e:
                logger.error(f"Failed to apply {f}: {e}")
                await self.rollback()
                return False

        try:
            with open(self.version_file, "w") as f:
                f.write(self.remote_version)
            logger.info(f"Version updated to {self.remote_version}")
        except Exception as e:
            logger.warn(f"Failed to write version file: {e}")

        try:
            with open(f"{self.ota_dir}/manifest.json") as src:
                manifest_data = json.load(src)
            with open("/manifest.json", "w") as dst:
                dst.write(json.dumps(manifest_data))
            logger.info("📄 manifest.json copied and formatted at root")
            with open("/version.txt") as f:
                version_txt = f.read().strip()
            manifest_version = manifest_data.get("version", "")
            if manifest_version != version_txt:
                logger.warn(f"⚠️ Version mismatch: manifest={manifest_version}, version.txt={version_txt}")
        except Exception as e:
            logger.warn(f"Could not write or verify manifest.json: {e}")

        await self.cleanup()

        try:
            os.rename("ota_pending.flag", "ota_commit_pending.flag")
            logger.info("📛 Renamed ota_pending.flag → ota_commit_pending.flag")
        except Exception as e:
            logger.warn(f"Could not rename ota_pending.flag: {e}")

        return True
    
    #--------------------------------------------------------------------------#
    async def rollback(self):
        for f in self.files:
            if f in self.user_excluded:
                logger.info(f"⚠️ Skipping rollback for user-preserved file: {f}")
                continue
            bkp = f"{self.backup_dir}/{f}"
            dst = f"/{f}"
            try:
                with open(bkp, "rb") as r, open(dst, "wb") as w:
                    w.write(r.read())
                logger.info(f"Rollback: {f}")
            except Exception as e:
                logger.error(f"Rollback failed: {f}: {e}")

        try:
            if "ota_pending.flag" in os.listdir("/"):
                os.remove("ota_pending.flag")
                logger.info("🗑 ota_pending.flag removed after rollback")
        except Exception as e:
            logger.warn(f"Could not remove ota_pending.flag during rollback: {e}")

        logger.info("✅ Rollback complete. Previous firmware restored.")
    
    #--------------------------------------------------------------------------#
    def _rmtree(self, path):
        for item in os.listdir(path):
            full_path = f"{path}/{item}"
            try:
                mode = os.stat(full_path)[0]
                if mode & 0x4000:
                    self._rmtree(full_path)
                    os.rmdir(full_path)
                else:
                    os.remove(full_path)
            except Exception as e:
                logger.warn(f"Could not remove {full_path}: {e}")
                
    #--------------------------------------------------------------------------#
    async def cleanup(self):
        try:
            self._rmtree(self.ota_dir)
            os.rmdir(self.ota_dir)
            logger.info("Cleaned up OTA directory")
        except Exception as e:
            logger.warn(f"Failed to clean up OTA directory: {e}")
            
    #--------------------------------------------------------------------------#
    def get_required_flash_bytes(self):
        return sum(self.sizes.get(f, 0) for f in self.files) * 2