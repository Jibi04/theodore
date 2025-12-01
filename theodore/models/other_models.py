from theodore.models.base import create_tables, meta
from theodore.core.utils import error_logger, base_logger, local_tz
from sqlalchemy import Table, Column, String, DateTime, Boolean
from datetime import datetime
import asyncio 

Queues = Table(
    'queues',
    meta,
    Column('func_name', String, primary_key=True, nullable=False),
    Column('args', String(100), nullable=False),
    Column('message', String(100)),
    Column('data', Boolean, default=False),
    Column('date', DateTime(timezone=local_tz)),
)

File_logs = Table(
    'file_logs',
    meta,
    Column('filename', String, primary_key=True, nullable=False),
    Column('source', String(100), nullable=False),
    Column('destination', String(100)),
    Column('is_downloaded', Boolean, default=False),
    Column('timestamp', DateTime(timezone=local_tz)),
)

def create_table():
    try:
        base_logger.internal('Creating configs table')

        asyncio.run(create_tables())
        base_logger.internal('Other tables created')
    except Exception as e:
        error_logger.exception(e)

create_table()