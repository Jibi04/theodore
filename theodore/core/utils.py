import dateparser 
import re
from rich.table import Table
from sqlalchemy import Table as sql_table
from pathlib import Path
from theodore.core.logger_setup import base_logger, error_logger
import tempfile
from zoneinfo import ZoneInfo
from urllib.parse import unquote, urlparse


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
from sqlalchemy import select, insert, update, delete, and_, or_
from sqlalchemy.exc import SQLAlchemyError

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

    async def update_features(self, values: dict, and_conditions: dict = None, or_conditions: dict = None) -> None:
        """update values in your db and commits asynchronously"""
        if not isinstance(self.table, sql_table):
            raise TypeError(f"Expected a Table class got {type(self.table)}.")
        
        stmt = update(self.table)
        final_conditions = self._sort_conditions(and_conditions, or_conditions)
        if final_conditions: stmt = stmt.where(*final_conditions)

        async with get_async_session() as session:
            try:
                stmt = stmt.values(values)
                await session.execute(stmt)
                await session.commit()
                return 
            except Exception as e:
                user_error(f'Database Update Query Failed: {e}')
                await session.rollback()
                raise

    async def insert_features(self, values: list[dict]) -> list[tuple]:
        """update values in your db and commits asynchronously"""
        if not isinstance(self.table, sql_table):
            raise TypeError(f"Expected a Table class got {type(self.table)}.")
        
        stmt = insert(self.table)

        async with get_async_session() as session:
            try:
                stmt = stmt.values(values)
                await session.execute(stmt)
                await session.commit()
                return 
            except Exception as e:
                user_error(f'Database Insert Query Failed: {e}')
                await session.rollback()
                raise

    async def delete_features(self, and_conditions: dict, or_conditions: dict) -> None:
        """deletes db rows commits asynchronously"""
        if not isinstance(self.table, sql_table):
            raise TypeError(f"Expected a Table class got {type(self.table)}.")
        
        stmt = delete(self.table)
        final_conditions = self._sort_conditions(and_conditions, or_conditions)
        if final_conditions: 
            stmt = stmt.where(*final_conditions)

        async with get_async_session() as session:
            try:
                await session.execute(stmt)
                await session.commit()
                return 
            except Exception as e:
                user_error(f'Database Delete Query Failed: {e}')
                await session.rollback()
                raise

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

    def parse_url(self, url: str, full_path: Path=None) -> dict:
        """
        Parses urls using unqote and urlparse
        return url filename
        """
        return_map = {}

        url_name = Path(unquote(urlparse(url).path)).name
        return_map['url'] = url
        return_map['filename'] = url_name
        if full_path: return_map['filepath'] = full_path / url_name
        
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
                await db_manager.insert_features(values=values)
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
    
