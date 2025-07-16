from typing import Any, Dict
import json
import os
import time
import shutil
import aiofiles
import asyncio
from threading import Lock
from datetime import datetime

async def record_open_trade(*args, **kwargs) -> None:
    # Stub: Replace with real trade recording logic
    return None

async def load_state(*args, **kwargs) -> Dict[str, Any]:
    # Stub: Replace with real state loading logic
    return {}

STATE_FILE = "trade_state.json"
BACKUP_DIR = "state_backups"
MAX_BACKUPS = 12
file_lock = Lock()

class StateManager:
    def __init__(self):
        self.state: Dict[str, Any] = {}
        self.last_save_time = 0
        os.makedirs(BACKUP_DIR, exist_ok=True)
        self._integrity_check()

    def _integrity_check(self) -> None:
        if not os.path.exists(STATE_FILE):
            self._write_state_sync({})
        try:
            with open(STATE_FILE, "r") as f:
                json.load(f)
        except Exception:
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
            corrupted_name = f"corrupted_{timestamp}.json"
            shutil.copy(STATE_FILE, corrupted_name)
            self._write_state_sync({})

    def load_state(self) -> None:
        with file_lock:
            try:
                with open(STATE_FILE, "r") as f:
                    self.state = json.load(f)
            except Exception:
                self.state = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.state[key] = value

    def delete(self, key: str) -> None:
        if key in self.state:
            del self.state[key]

    def get_all(self) -> Dict[str, Any]:
        return self.state

    def save(self) -> None:
        asyncio.create_task(self._save_async())

    async def _save_async(self) -> None:
        async with asyncio.Lock():
            try:
                tmp_path = f"{STATE_FILE}.tmp"
                async with aiofiles.open(tmp_path, "w") as f:
                    await f.write(json.dumps(self.state, indent=2))
                os.replace(tmp_path, STATE_FILE)
                self._maybe_backup()
            except Exception as e:
                print(f"Failed to save state: {e}")

    def _write_state_sync(self, state: Dict[str, Any]) -> None:
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Sync write failed: {e}")

    def _maybe_backup(self) -> None:
        now = time.time()
        if now - self.last_save_time > 300:
            self.last_save_time = now
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
            backup_file = os.path.join(BACKUP_DIR, f"state_{timestamp}.json")
            try:
                shutil.copy(STATE_FILE, backup_file)
            except Exception as e:
                print(f"Backup failed: {e}")
            self._trim_backups()

    def _trim_backups(self) -> None:
        files = sorted(os.listdir(BACKUP_DIR))
        while len(files) > MAX_BACKUPS:
            old_file = files.pop(0)
            try:
                os.remove(os.path.join(BACKUP_DIR, old_file))
            except Exception:
                continue
