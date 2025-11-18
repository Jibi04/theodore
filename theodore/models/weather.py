import asyncio

from sqlalchemy import Table, Column, String, Float , ForeignKey 
from theodore.models.base import meta , engine, create_tables
from theodore.core.utils import base_logger, error_logger


Weather = Table(
    'Weather',
    meta,
    Column('country', String),
    Column('city', String),
    Column('condition', String),
    Column('temp_C', Float),
    Column('temp_F', Float),
    Column('humidiy', String),
    Column('wind_Speed', Float),
    Column('wind_direction', String),
    
)


Alerts = Table(
    'Alerts',
    meta,
    Column('headline', String),
    Column('event', String),
    Column('certainty', String),
    Column('urgency', String),
    Column('severity', String),
    Column('note', String),
    Column('effective', String),
    Column('description', String),
    Column('instructions', String),
    Column('city', ForeignKey('Weather.city'))
)

Forecasts = Table(
    'Forecasts',
    meta,
    Column('sunrise_at', String),
    Column('sunset_at', String),
    Column('moonrise_at', String),
    Column('moonset_at', String),
    Column('avg_temp_f', String),
    Column('avg_temp_c', String),
    Column('max_temp_f', String),
    Column('max_temp_c', String),
    Column('min_temp_f', String),
    Column('min_temp_c', String),
    Column('chance_of_rain', String),
    Column('chance_of_snow', String),
    Column('will_it_rain', String),
    Column('city', ForeignKey('Weather.city'))
)

# ctrl + shift + u + 00b0 + ENTER


def create_table():
    try:
        base_logger.internal('Creating tasks table(s)')

        asyncio.run(create_tables())
        base_logger.internal('Task table created')

    except Exception as e:
        error_logger.exception(e)

# create_table()