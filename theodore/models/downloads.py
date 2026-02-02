from sqlalchemy import Column, String, DateTime, Boolean, Table, Integer
from theodore.models.base import meta


DownloadTable= Table(
    'download_manager',
    meta,
    Column('filename', String, nullable=False),
    Column('url', String),
    Column('is_downloaded', Boolean, default=False),
    Column('filepath', String),
    Column('download_percentage', Integer),
    Column('date_downloaded', DateTime(True))
)
