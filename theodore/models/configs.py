from theodore.models.base import create_tables, meta
from theodore.core.utils import error_logger, base_logger
from sqlalchemy import Table, Column, String
import asyncio 


ConfigTable = Table(
    'configs',
    meta,
    Column('category', String, primary_key=True, nullable=False),
    Column('default_path', String(100)),
    Column('default_location', String(100)),
    Column('api_key', String(150)),
)

# def create_table():
#     try:
#         base_logger.internal('Creating configs table')

#         asyncio.run(create_tables())
#         base_logger.internal('Configs table created')
#     except Exception as e:
#         error_logger.exception(e)

# create_table()