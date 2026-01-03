import dateparser 
import re
from rich.table import Table
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


def get_current_weather_table(**kwargs):
    pass

from theodore.models.base import get_async_session
from sqlalchemy import select, insert, update, delete, and_, or_
from sqlalchemy.exc import SQLAlchemyError

class DB_tasks:
    """
    Write, update, delete, select rows and feartures from your db, Asynchronously
    """
    def __init__(self, table: Table):
        self.table = table

    def __enter__(self):
        return self
    
    def _get_conditions(self, conditions_dict: dict) -> list:
            if not conditions_dict: 
                return []
            
            conditionals = []
            try:
                for key, value in conditions_dict.items():
                    Column = getattr(self.table, key)
                    if Column: 
                        conditionals.append(Column == value)
                return conditionals
            except AttributeError as e:
                raise AttributeError(
                    f"Column '{key}' non-existent on table '{self.table.name}'. "
                    f"Original Error: {e}"
                    )

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

    async def get_features(self, and_conditions: dict = None, or_conditions: dict = None) -> list[tuple]:
        """
        select the values of your in your Database
        reuturns a list of query tuples
        """
        if not isinstance(self.table, Table):
            raise TypeError(f"Expected a Table class got {type(self.table)}.")
        
        stmt = select(self.table)
        final_conditions = self._sort_conditions(and_conditions, or_conditions)
        if final_conditions: stmt = stmt.where(*final_conditions)

        async with get_async_session() as session:
            try:
                results = await session.execute(stmt)
                return results.all()
            except Exception as e:
                user_error(f'Database Select Query Failed: {e}')
                await session.rollback()
                raise

    async def update_features(self, values: list[dict], and_conditions: dict = None, or_conditions: dict = None) -> None:
        """update values in your db and commits asynchronously"""
        if not isinstance(self.table, Table):
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
        if not isinstance(self.table, Table):
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

    async def delete_features(self, and_conditions: dict, or_conditions: dict):
        """deletes db rows commits asynchronously"""
        if not isinstance(self.table, Table):
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
    def __init__(self, downloader_class):
        self.file_downloader = downloader_class

    def parse_url(self, url: str) -> str:
        """
        Parses urls using unqote and urlparse
        return url filename
        """
        return Path(unquote(urlparse(url).path)).name

    async def get_undownloaded_urls(self) -> list[str] | list:
        """
        Queries db for undownloded files
        returns list
        """
        async with get_async_session() as session:
            stmt = select(self.file_downloader.c.url).where(self.file_downloader.c.is_downloaded.is_(False))
            result = await session.execute(stmt)
            return result.scalars().all()
        return []

    async def bulk_insert(self, table: Table, values: list[dict]) -> None:
        """
        Insert values into table
        Args:
            table: DB table variable
            values: key value dict objects of table column and entries
        returns None
        """
        try:
            async with get_async_session() as session:
                with DB_tasks(self.file_downloader) as db_manager:
                    await db_manager.insert_features(values=values)
                    return  
        except SQLAlchemyError:
            raise
        
    async def get_full_name(self, filename):
        async with get_async_session() as session:
            stmt = select(self.file_downloader.c.filename.ilike(f'{filename}%')).where(self.file_downloader.c.is_downloaded.is_(False))
            results = await session.execute(stmt)
        filenames = results.scalars().all()
        return filenames
    
    def __repr__(self):
        return f"Downloads(table={self.file_downloader.name})"
    
    def __str__(self):
        return f"table name '{self.file_downloader.name}'"
    
