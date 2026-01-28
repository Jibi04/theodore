from theodore.models.base import meta
from theodore.core.utils import local_tz
from sqlalchemy import Table, Column, String, DateTime, Boolean, TIMESTAMP, BLOB

Queues = Table(
    'queues',
    meta,
    Column('func_name', String, primary_key=True, nullable=False),
    Column('args', String(100), nullable=False),
    Column('message', String(100)),
    Column('data', Boolean, default=False),
    Column('date', DateTime(timezone=local_tz)),
)

FileLogsTable = Table(
    'file_logs',
    meta,
    Column('filename', String, primary_key=True, nullable=False),
    Column('source', String(100), nullable=False),
    Column('destination', String(100)),
    Column('is_downloaded', Boolean, default=False),
    Column('timestamp', DateTime(timezone=local_tz)),
)

LOGSEARCH = Table(
    "logs",
    meta,
    Column('timestamp', TIMESTAMP, nullable=False),
    Column('level', String(20), nullable=False),
    Column('message', String(256)),
    Column('vector', BLOB)
)

