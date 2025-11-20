import json
import time
from datetime import datetime


from pathlib import Path
from theodore.core.utils import send_message, DATA_DIR, local_tz
from theodore.core.logger_setup import base_logger


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
        
        base_logger.internal('Loading cache file')
        key = key.lower()
        entry = self.cache.get(key, None)

        if not entry:
            base_logger.debug(f'Cache manager returned {entry}')
            return

        base_logger.internal('filtering recent cache data')
        old_time = entry['ttl_stamp']
        new_time = time.monotonic()
        time_difference = new_time - old_time

        if time_difference > self.ttl:
            base_logger.debug(f"No unexpired data from timeline {time_difference} > {self.ttl}")
            return
        
        weather_data = entry['data']
        base_logger.debug(f"Cache manager returned {weather_data}")
        return weather_data
    
    def clear_cache(self):
        self.cache = {}
        return
    
    def set_cache(self, key, data):
        key = key.lower()
        try:

            if key in self.cache:
                self.cache[key]['data'].update(data)
            else:
                self.cache[key] = {"ttl_stamp": time.monotonic(), "timestamp": datetime.now(local_tz).isoformat(), f"data": data}
            
            self._save_cache()
            return send_message(True, message='Cache created')
        except json.JSONDecodeError as e:
            return send_message(False, message=f"A Json decode error occured {str(e)}")
