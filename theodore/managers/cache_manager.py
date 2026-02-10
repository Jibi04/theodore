import json, time
from typing import Dict, Literal
from datetime import datetime

from sqlalchemy import select, insert, update
from sqlalchemy.exc import SQLAlchemyError
from theodore.models.base import get_async_session
from theodore.models.other_models import FileLogsTable
from theodore.models.weather import Current, Alerts, Forecasts
from theodore.core.logger_setup import base_logger
from theodore.core.paths import DATA_DIR
from theodore.core.time_converters import get_localzone
from theodore.core.informers import send_message


CACHE_DIR = DATA_DIR / "cache"

CACHE_DIR.mkdir(parents=True, exist_ok=True)

FILE_PATH = CACHE_DIR / 'weather.cache'




class Cache_manager:
    """Loads weather and File cache"""
    def __init__(self, ttl):
        self.ttl = ttl
        self.cache = self._load_cache()

        self.registry = {
            "current": [select(Current), insert(Current), update(Current)],
            "alerts": [select(Alerts), insert(Alerts), update(Alerts)],
            "forecasts": [select(Forecasts), insert(Forecasts), update(Forecasts)],
            "filelogs": [select(FileLogsTable), insert(FileLogsTable), update(FileLogsTable)]
        }

    async def load_cache(self, category: Literal["current", "alerts", "forecasts", "filelogs"] ) -> Dict:
        try:
            async with get_async_session() as conn:
                if (record:=self.registry.get(category)) is None:
                    raise ValueError(f"Category {category} not recognized")
                
                query = record[0]
                db_response = await conn.execute(query)
                return send_message(True, data=db_response.mappings().all())
        except SQLAlchemyError as err:
            return send_message(False, message=f"unable to load cache {str(err)}")

    async def create_new_cache(self, data , category: Literal["current", "alerts", "forecasts", "filelogs"] , bulk=False, *args) -> Dict:
        try:
            async with get_async_session() as conn:
                if bulk:
                    if not args:
                        send_message(False, message='Cannot bulk insert without tablename and list of insert-values')
                    table, values = args
                    query = insert(table.capitalize())
                    db_response = await conn.execute(query, values)
                else:
                    if not data: return send_message(False, message="Cannot create cache, no values to insert")
                    if (record:=self.registry.get(category)) is None:
                        raise ValueError(f"Category {category} not recognized")
                
                    query = record[1]
                    query = query.values(data)
                    db_response = await conn.execute(query)
                await conn.commit()
                return send_message(True, data=db_response.rowcount)
        except SQLAlchemyError as err:
            return send_message(False, message=f"unable to load cache {str(err)}")

    async def update_cache(self, data , category: Literal["current", "alerts", "forecasts", "filelogs"] , bulk=False, *args) -> Dict:
        try:
            async with get_async_session() as conn:
                if bulk:
                    if not args:
                        return send_message(False, message='Cannot bulk update without tablename and list of insert-values')
                    table, values = args
                    query = insert(table.capitalize())
                    db_response = await conn.execute(query, values)
                else:
                    if not data: return send_message(False, message="Cannot update cache, no values to update")
                    if (record:=self.registry.get(category)) is None:
                        raise ValueError(f"Category {category} not recognized")
                
                    query = record[2]
                    db_response = await conn.execute(query)
                await conn.commit()
                return send_message(True, data=db_response.rowcount)
        except SQLAlchemyError as err:
            return send_message(False, message=f"unable to load cache {str(err)}")
        
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
        
        base_logger.debug('Loading cache file')
        key = key.lower()
        record = self.cache.get(key, None)

        if not record:
            base_logger.debug(f'Cache manager returned {record}')
            return

        base_logger.debug('filtering recent cache data')
        old_time = record['ttl_stamp']
        new_time = time.monotonic()
        time_difference = new_time - old_time

        if time_difference > self.ttl:
            base_logger.debug(f"No unexpired data from timeline {time_difference} > {self.ttl}")
            return
        
        weather_data = record['data']
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
                self.cache[key] = {"ttl_stamp": time.monotonic(), "timestamp": datetime.now(get_localzone()).isoformat(), f"data": data}
            
            self._save_cache()
            return send_message(True, message='Cache created')
        except json.JSONDecodeError as e:
            return send_message(False, message=f"A Json decode error occured {str(e)}")