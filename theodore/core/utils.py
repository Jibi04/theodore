import dateparser 
import re, asyncio
from typing import Dict, Annotated, Literal
from rich.table import Table
from sqlalchemy import Table as sql_table
from pathlib import Path
from theodore.core.logger_setup import base_logger, error_logger
import tempfile
from zoneinfo import ZoneInfo
from urllib.parse import unquote, urlparse

from functools import partial
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime

# -------------------------
# Global Variables 
# -------------------------
local_tz = ZoneInfo("GMT")
DATA_DIR = Path(__file__).parent.parent / "data"

JSON_DIR = DATA_DIR / "json"
TEMP_DIR = Path(tempfile.gettempdir()) / "theodore_downloads"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
JSON_DIR.mkdir(parents=True, exist_ok=True)
FILE = JSON_DIR / "cache.json"

def user_success(msg):
    return base_logger.info(f'[success]{msg}')

def user_warning(msg):
    return base_logger.warning(f'[warning]{msg}')

def user_error(msg):
    return error_logger.error(f'[error]{msg}')

def user_info(msg):
    return base_logger.info(msg)

def send_message(ok, message=None, date=None, data=None):
    return {'ok': ok, 'message': message, 'data': data, 'date': date}

def normalize_ids(task_id = None, task_ids = None):
    ids = []

    if task_id: ids.append(task_id)
    if task_ids: ids.extend(re.split(r'\D+', task_ids))
    cleaned_ids = []
    for val in ids:
        try:
            cleaned_ids.append(int(val))
        except ValueError:
            continue
    return cleaned_ids

def parse_date(date: str) -> dict:
    date = dateparser.parse(date)
    if date is None:
        message = 'unable to parse date'
        return send_message(False, message)
    return send_message(True, 'Date Parsed', date=date)

def get_task_table(data, deleted=False):
    table = Table()
    table.min_width = 100
    table.title = 'Tasks'
    table.show_lines = True
    
    table.add_column(f'[bold]Task id[/]', no_wrap=True)
    table.add_column(f'[bold]Title[/]', no_wrap=True)
    table.add_column(f'[bold]Description[/]', no_wrap=True)
    table.add_column(f'[bold]Status[/]', no_wrap=True)
    table.add_column(f'[bold]Date Created[/]', no_wrap=True)
    table.add_column(f'[bold]Due Date[/]', no_wrap=True)
    if deleted:
        table.add_column(f'[bold]Date Deleted[/]', no_wrap=True)
    status_map = {"in_progress": "[green]", "pending": "[bold red]", "not_completed": "[bold cyan]"}
    for task in data:
        status = task.get("status")
        style = status_map.get(status, "[white]")
        task_id = f'{style}{task.get("task_id")}[/]'
        task_title = f'{style}{task.get("title")}[/]'
        description = task.get('description')

        description = f'{style}{"-".join((description).split(","))}[/]' if description else f'[bold cyan]{description}[/]'
        status = f'{style}{status}[/]'
        due_date = f'{style}{task.get("due")}[/]'
        date_created = f'{style}{str(task.get("date_created"))}[/]' 

        if deleted:
            date_deleted = f'{style}{str(task.get("date_deleted"))}[/]'
            row_data = (task_id, task_title, description, status, date_created, due_date, date_deleted)
        else:
            row_data = (task_id, task_title, description, status, date_created, due_date)

        table.add_row(*row_data)

    return table


def get_current_weather_table(**kwargs):
    pass

def get_configs_table(data):
    table = Table()
    table.min_width = 100
    table.title = 'Tasks'
    table.show_lines = True

    table.add_column('[bold]category[/]', no_wrap=True)
    table.add_column('[bold]default_path[/]', no_wrap=True)
    table.add_column('[bold]location[/]', no_wrap=True)
    table.add_column('[bold]api_key[/]', no_wrap=True)

    for row in data:
        table.add_row(
            row.category.capitalize(), 
            row.default_path, 
            row.default_location, 
            row.api_key if row.api_key else '[magenta bold]Not set[/]'
        )
    return table

def get_current_weather_table(**kwargs):
    pass

from theodore.models.base import get_async_session
from sqlalchemy import select, insert, update, delete, and_, or_, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

class DB_tasks:
    """
    Write, update, delete, select rows and feartures from your db, Asynchronously
    """
    def __init__(self, table: sql_table):
        if not isinstance(table, sql_table):
            raise AttributeError(f"This table is not an sql_table instance {type(table)}")
        self.table = table

    def __enter__(self):
        return self
    
    def _get_conditions(self, conditions_dict: dict) -> list:
            if not conditions_dict: 
                return []
            
            conditionals = []
            for key, value in conditions_dict.items():
                if hasattr(self.table.c, key):
                    Column = getattr(self.table.c, key)
                    conditionals.append(Column == value)
                else:
                    raise AttributeError(
                        f"Column '{key}' non-existent on table '{self.table.name}'. "
                        )
            return conditionals
    
    def _sort_conditions(self, and_conditions: dict, or_conditions: dict) -> list:
        """
        Sorts all conditions and returns a final conditions
        returns all sorted conditions as a list
        """
        and_list = self._get_conditions(and_conditions)
        or_list = self._get_conditions(or_conditions)
        
        final_conditions = []
        if and_list or or_list:

            if and_list:
                final_conditions.extend(and_list)
            if or_list:
                final_conditions.append(or_(*or_list))

        return final_conditions
    
    async def run_query(self, stmt, sudo=True, first=False, all=False, one=False, upsert=False, var_map={}):
        if not sudo:
            user_warning("Error: cannot perform task not sudo!")
            return send_message(False, message='Cannot perform task')
        query = text(stmt)
        async with get_async_session() as session:
            response = await session.execute(query, var_map)
            data = response
            if first:
                data = response.first()
            elif one:
                data = response.scalar()
            elif all:
                data = response.all()
            elif upsert:
                data = ''
            return send_message(True, data=data)

    async def get_features(self, and_conditions: dict = None, or_conditions: dict = None, first=False) -> list[tuple]:
        """Queries your DB Using SELECT with conditions as WHERE if conditions are None, returns all rows in the DB"""
        if not isinstance(self.table, sql_table):
            raise TypeError(f"Expected a Table class got {type(self.table)}.")
        
        stmt = select(self.table)
        final_conditions = self._sort_conditions(and_conditions, or_conditions)
        if final_conditions: stmt = stmt.where(*final_conditions)

        async with get_async_session() as session:
            try:
                results = await session.execute(stmt)
                if first:
                    return results.first()
                else:
                    rows = results.all()
                    return rows
            except Exception as e:
                user_error(f'Database Select Query Failed: {e}')
                await session.rollback()
                raise

    async def upsert_features(self, values: Dict, primary_key: Dict = None, bulk: bool=False) -> Dict:
        async with get_async_session() as session:
            try:
                if not isinstance(values, (dict, list)):
                    raise TypeError(f'Expected \'{dict.__name__}\' but got \'{type(values)}\'.')
                stmt = insert(self.table).values(values)
                await session.execute(stmt)
            except IntegrityError:
                key, val  = primary_key or next(iter(values), {})
                stmt = update(self.table).where(key == val).values(values)
                await session.execute(stmt)
            finally:
                await session.commit()
                await session.close()
            return send_message(True, message='Done!')

    async def permanent_delete(self, or_conditions, and_conditions, query = None) -> None:
        final_conditions = self._sort_conditions(or_conditions=or_conditions, and_conditions=and_conditions)
        stmt = select(self.table).where(*final_conditions)

        async with get_async_session() as session:
            try:
                await session.execute(stmt)
                await session.commit()
            except SQLAlchemyError as e:
                await session.rollback()
                user_error(f"Database Delete Not done: {e}")
        return

    async def delete_features(self, and_conditions: dict, or_conditions: dict = {}) -> None:
        """deletes db rows commits asynchronously"""
        final_conditions = self._sort_conditions(and_conditions, or_conditions)
        stmt = delete(self.table).where(*final_conditions)

        async with get_async_session() as session:
            try:
                await session.execute(stmt)
                await session.commit()
                return 
            except Exception as e:
                user_error(f'Database Delete Query Failed: {e}')
                await session.rollback()
                raise
        return

    async def exists(self, **kwargs) -> bool:
        async with get_async_session() as session:
            stmt = select(1).select_from(self.table).filter_by(**kwargs).limit(1)
            result = await session.execute(stmt)
            return result.scalar() is not None


    def __repr__(self):
        return f"DB_tasks(table={self.table.name})"
    
    def __str__(self):
        return f"table name '{self.table.name}'"
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            return False
        
        # Exceptions should be handled by the client
        return False


class Downloads:
    def __init__(self, table: sql_table):
        self.file_downloader = table

    def parse_url(self, url: str, full_path: Path) -> dict:
        """
        Parses urls using unqote and urlparse
        return url filename
        """
        return_map = {}

        url_name = Path(unquote(urlparse(url).path)).name
        return_map['url'] = url
        return_map['filename'] = url_name
        return_map['filepath'] = f"{full_path}/{url_name}"
        
        return return_map

    async def get_undownloaded_urls(self) -> list[str] | list:
        """
        Queries db for undownloded files
        returns list
        """
        async with get_async_session() as session:
            stmt = (select(self.file_downloader.c.url)
                    .where(
                        self.file_downloader.c.is_downloaded.is_(False)
                        )
                    )
            result = await session.execute(stmt)
            return result.scalars().all()
        return []
    
    async def get_download_status(self, conditions):
        """get a single feature"""
        if not isinstance(self.table, sql_table):
            raise TypeError(f"Expected a Table class got {type(self.table)}.")
        final_conditions = []
        for key, val in conditions.items():
            if hasattr(self.file_downloader.c, key):
                Column = getattr(self.file_downloader, key)
                final_conditions.append(Column == val)
            else:
                raise AttributeError(
                    f"Column '{key}' non-existent on table '{self.table.name}'. "
                    )
        async with get_async_session() as session:
            stmt = (select(self.file_downloader.c.download_percentage).where(*final_conditions).limit(1))
            response = await session.execute(stmt)
            return response.scalar_one_or_none()

    async def bulk_insert(self, table: Table, values: list[dict]) -> None:
        """
        Insert values into table
        Args:
            table: DB table variable
            values: key value dict objects of table column and entries
        returns None
        """
        try:
            with DB_tasks(table) as db_manager:
                await db_manager.upsert_features(values=values)
        except SQLAlchemyError:
            raise
        
    async def get_full_name(self, filename):
        async with get_async_session() as session:
            stmt = (select(self.file_downloader.c.filename)
                    .where(
                        self.file_downloader.c.filename.ilike(f'{filename}%'),
                        self.file_downloader.c.is_downloaded.is_(False)
                        )
                    .limit(1)
                )
            results = await session.execute(stmt)
            return results.scalar_one_or_none()
    
    def __repr__(self):
        return f"Downloads(table={self.file_downloader.name})"
    
    def __str__(self):
        return f"table name '{self.file_downloader.name}'"
    
class WeatherModel(BaseModel):
    model_config = ConfigDict(extra='ignore')
    city: str
    country: str
    time_requested: Annotated[datetime, Field(default_factory=partial(datetime.now, tz=local_tz))]

class Current_(WeatherModel):
    model_config = ConfigDict(extra='ignore')

    text: Annotated[str | None, Field(alias='text')]
    temp_c: Annotated[float, Field(alias='temp_c')]
    feels_c: Annotated[float, Field(alias='feels_c')]
    temp_f: Annotated[float, Field(alias='temp_f')]
    feels_f: Annotated[float, Field(alias='feels_f')]
    humidity: Annotated[str, Field(alias='humidity')]
    wind_kph: Annotated[float, Field(alias='wind_kph')]
    wind_mph: Annotated[float, Field(alias='wind_mph')]
    wind_dir: Annotated[float, Field(alias='wind_dir')]

class Alerts_(WeatherModel):
    model_config = ConfigDict(extra='ignore')

    headline: Annotated[str | None, Field(alias='headline')]
    event: Annotated[str | None, Field(alias='event')]
    certainty: Annotated[str | None, Field(alias='certainty')]
    urgency: Annotated[str | None, Field(alias='urgency')]
    severity: Annotated[str | None, Field(alias='severity')]
    note: Annotated[str | None, Field(alias='note')]
    effective: Annotated[str | None, Field(alias='effective')]
    description: Annotated[str | None, Field(alias='description')]
    instructions: Annotated[str | None, Field(alias='instructions')]


class Forecast_(WeatherModel):
    model_config = ConfigDict(extra='ignore')

    sunrise: Annotated[datetime, Field(alias='sunrise')]
    sunset: Annotated[datetime, Field(alias='sunset')]
    moonrise: Annotated[datetime, Field(alias='moonrise')]
    moonset: Annotated[datetime, Field(alias='moonset')]
    min_temp_c: Annotated[float, Field(alias='min_temp_c')]
    max_temp_c: Annotated[float, Field(alias='max_temp_c')]
    avg_temp_c: Annotated[float, Field(alias='avg_temp_c')]
    min_temp_f: Annotated[float, Field(alias='min_temp_f')]
    max_temp_f: Annotated[float, Field(alias='max_temp_f')]
    avg_temp_f: Annotated[float, Field(alias='avg_temp_f')]
    maxwind_kph: Annotated[float, Field(alias='maxwind_kph')]
    avgvis_km: Annotated[float, Field(alias='avgvis_km')]
    maxwind_mph: Annotated[float, Field(alias='maxwind_mph')]
    avgvis_miles: Annotated[float, Field(alias='avgvis_miles')]
    daily_chance_of_rain: Annotated[float, Field(alias='daily_chance_of_rain')]
    daily_chance_of_snow: Annotated[float, Field(alias='daily_chance_of_snow')]
    daily_will_it_rain: Annotated[bool | int, Field(alias='daily_will_it_rain')]
    daily_will_it_snow: Annotated[bool | int, Field(alias='daily_will_it_snow')]