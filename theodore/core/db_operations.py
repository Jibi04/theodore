from pathlib import Path
from typing import Dict
from urllib.parse import unquote, urlparse

from theodore.core.informers import *
from theodore.models.base import get_async_session
from sqlalchemy import select, insert, update, delete, or_, text, Table, Sequence, Row
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

class DBTasks:
    """
    Write, update, delete, select rows and feartures from your db, Asynchronously
    """
    def __init__(self, table: Table):
        if not isinstance(table, Table):
            raise AttributeError(f"This table is not an Table instance {type(table)}")
        self.table = table

    def __enter__(self):
        return self
    
    def _get_conditions(self, conditions_dict: dict | None) -> list:
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
    
    def _sort_conditions(self, and_conditions: dict | None, or_conditions: dict | None) -> list:
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

    async def get_features(self, and_conditions: dict | None = None, or_conditions: dict | None= None, first = False) -> Sequence[Row[Any]] | Row[Any] | None:
        """Queries your DB Using SELECT with conditions as WHERE if conditions are None, returns all rows in the DB"""
        if not isinstance(self.table, Table):
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

    async def upsert_features(self, values: Dict | list, primary_key: Dict | None = None, bulk: bool=False) -> Dict:
        async with get_async_session() as session:
            try:
                if not isinstance(values, (dict, list)):
                    raise TypeError(f'Expected \'{dict.__name__}\' but got \'{type(values)}\'.')
                stmt = insert(self.table).values(values)
                await session.execute(stmt)
                return send_message(True, message='Done!')
            except IntegrityError:
                if primary_key is None:
                    raise ValueError("Cannot update database without a known key-value condition")
                if not isinstance(primary_key, dict):
                    raise TypeError(f"Expected a Dict object got a {type(primary_key)}.")

                conditions = self._get_conditions(conditions_dict=primary_key)
                if not conditions:
                    raise ValueError(f"Cannot update tasks unknown primary values.")
                stmt = update(self.table).where(*conditions).values(values)
                await session.execute(stmt)
                return send_message(True, message='Done!')
            finally:
                await session.commit()
                await session.close()

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
        return f"DBTasks(table={self.table.name})"
    
    def __str__(self):
        return f"table name '{self.table.name}'"
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            return False
        
        # Exceptions should be handled by the client
        return False


class Downloads:
    def __init__(self, table: Table):
        self.table = table

    def parse_url(self, url: str, full_path: Path | str = "~/Downloads") -> dict:
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

    async def get_undownloaded_urls(self) -> Sequence[str]:
        """
        Queries db for undownloded files
        returns list
        """
        async with get_async_session() as session:
            stmt = (select(self.table.c.url)
                    .where(
                        self.table.c.is_downloaded.is_(False)
                        )
                    )
            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def get_download_status(self, conditions):
        """get a single feature"""
        if not isinstance(self.table, Table):
            raise TypeError(f"Expected a Table class got {type(self.table)}.")
        final_conditions = []
        for key, val in conditions.items():
            if hasattr(self.table.c, key):
                Column = getattr(self.table, key)
                final_conditions.append(Column == val)
            else:
                raise AttributeError(
                    f"Column '{key}' non-existent on table '{self.table.name}'. "
                    )
        async with get_async_session() as session:
            stmt = (select(self.table.c.download_percentage).where(*final_conditions).limit(1))
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
        with DBTasks(table) as db_manager:
            await db_manager.upsert_features(values=values)
        
    async def get_full_name(self, filename):
        async with get_async_session() as session:
            stmt = (select(self.table.c.filename)
                    .where(
                        self.table.c.filename.ilike(f'%{filename}%'),
                        self.table.c.is_downloaded.is_(False)
                        )
                    .limit(1)
                )
            results = await session.execute(stmt)
            return results.scalar_one_or_none()
    
    def __repr__(self):
        return f"Downloads(table={self.table.name})"
    
    def __str__(self):
        return f"table name '{self.table.name}'"