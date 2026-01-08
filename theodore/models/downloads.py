from sqlalchemy import Column, String, DateTime, Boolean, Table, delete, Integer
from theodore.models.base import meta, engine
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
    Column('download_percentage', Integer),
    Column('date_downloaded', DateTime(local_tz))
)
