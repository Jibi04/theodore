from sqlalchemy import Column, String, DateTime, Boolean, Table, delete
from .base import meta, engine
from theodore.core.utils import local_tz, base_logger, user_success
from datetime import datetime
import asyncio

file_downloader = Table(
    'download_manager',
    meta,
    Column('filename', String, nullable=False),
    Column('url', String),
    Column('is_downloaded', Boolean, default=False),
    Column('filepath', String),
    Column('date_downloaded', DateTime(local_tz))
)
# async def drop_table(table: Table):
#     async with engine.begin() as conn:
#         await conn.run_sync(lambda sync_conn: table.drop(sync_conn))
#     user_success(f'{table.name} dropped')

# asyncio.run(drop_table(file_downloader))

# async def create_tables():
#     base_logger.internal('Connecting to the database engine')
#     async with engine.begin() as conn:
#         base_logger.internal('Creating all db tables')
#         await conn.run_sync(meta.create_all)
