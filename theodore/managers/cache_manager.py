import json
import time
from datetime import datetime


from pathlib import Path
from theodore.core.utils import send_message, DATA_DIR, local_tz


CACHE_DIR = DATA_DIR / "cache"

CACHE_DIR.mkdir(parents=True, exist_ok=True)

FILE_PATH = CACHE_DIR / 'weather.cache'


class Cache_manager:

    def __init__(self, ttl):
        self.ttl = ttl
        self.cache = self._load_cache()

    def _load_cache(self):
        if FILE_PATH.exists():
            try:

                data = json.loads(FILE_PATH.read_text())
                return data

            except json.JSONDecodeError:
                return {}
            
        return {}
    
    def _save_cache(self):
        FILE_PATH.write_text(json.dumps(self.cache, indent=4))
        return
    
    def get_cache(self, key):
        if not self.cache:
            return None

        key = key.lower()
        entry = self.cache.get(key)

        if not entry:
            return None

        if time.time() - entry['Timestamp'] > self.ttl:
            return None
        
        return entry['data']
    
    def set_cache(self, key, data):
        key = key.lower()
        try:

            if key in self.cache:
                self.cache[key]['data'].update(data)
            else:
                self.cache[key] = {"Timestamp": time.time(), "timestamp": datetime.now(local_tz).isoformat(), f"data": data}
            
            self._save_cache()
            return send_message(True, message='Cache created')
        except json.JSONDecodeError as e:
            return send_message(False, message=f"A Json decode error occured {str(e)}")
