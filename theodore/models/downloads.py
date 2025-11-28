from sqlalchemy import Column, String, DateTime, Boolean, Table
from .base import meta, engine
from theodore.core.utils import local_tz, base_logger
from datetime import datetime

file_downloader = Table(
    'download_manager',
    meta,
    Column('filename'),
    Column('url', String),
    Column('is_downloaded', Boolean),
    Column('filepath', String),
    Column('date_downloaded', DateTime(local_tz))
)

async def create_tables():
    base_logger.internal('Connecting to the database engine')
    async with engine.begin() as conn:
        base_logger.internal('Creating all db tables')
        await conn.run_sync(meta.create_all)
