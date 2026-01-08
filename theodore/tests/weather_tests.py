from typing import List, AnyStr, Dict
from sqlalchemy import Table, insert, update, select, text
from sqlalchemy.exc import IntegrityError
from theodore.models.base import AsyncSession

async def upsert1(table: Table, values: Dict, conditions: Dict = None) -> Dict:
    """"update or insert values into db, primary_key should always be first values inserted"""
    def sort_conditions(conditions):
        final_conditions = []
        for key, val in conditions.items():
            if not hasattr(table, key):
                continue
            column = getattr(table, key)
            final_conditions.append(column == val)
        return final_conditions
        
    async with AsyncSession() as session:
        primary_item = next(iter(values))
        peek_stmt = select(1).select_from(table).filter_by(**primary_item).limit(1)
        result = await session.execute(peek_stmt)
        if result.scalar() is None:
            stmt = insert(table).values(values)
        else:
            sorted_conditions = sort_conditions(conditions=conditions)
            stmt = update(table).where(*sorted_conditions).values(values)
        await session.execute(stmt)


async def upsert2(table: Table, values: Dict) -> Dict:
    async with AsyncSession() as session:
        try:
            if not isinstance(values, dict):
                raise TypeError(f'Expected \'{dict.__name__}\' but got \'{type(values)}\'.')
            stmt = insert(table).values(values)
            await session.execute(stmt)
        except IntegrityError:
            key, val  = next(iter(values), {})
            stmt = update(table).where(key == val).values(values)
            await session.execute(stmt)
        finally:
            await session.commit()
            await session.close()
        return
