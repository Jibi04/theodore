import asyncio
from sqlalchemy import Table, Column, String, Boolean, Integer, DateTime # , ForeignKey , insert, update, delete, select
from theodore.models.base import meta , engine, create_tables
from datetime import datetime, timezone
from theodore.core.utils import base_logger, error_logger


Tasks = Table(
    'tasks',
    meta, 
    Column('task_id', Integer, primary_key=True, autoincrement=True),
    Column('title', String(50), nullable=False),
    Column('description', String(250)),
    Column('date_created', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    Column('status', String(230), default='pending'),
    Column('due', DateTime(timezone=True)),
    Column('is_deleted', Boolean,  default=False),
    Column('date_deleted', DateTime(timezone=True)),
)


# Tags = Table(
#     'tags',
#     meta,
#     Column('tag_id', Integer, autoincrement=True, primary_key=True),
#     Column('description', String(500), nullable=False),
#     Column('client_id', Integer, ForeignKey('Tasks.id'))
# )


def create_table():
    try:
        base_logger.internal('Creating tasks table(s)')

        asyncio.run(create_tables())
        base_logger.internal('Task table created')

    except Exception as e:
        error_logger.exception(e)

# create_table()