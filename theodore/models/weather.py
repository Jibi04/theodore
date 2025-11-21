import asyncio
from datetime import datetime
from sqlalchemy import Table, Column, String, Float , ForeignKey, DateTime
from theodore.models.base import meta, create_tables
from theodore.core.utils import base_logger, error_logger, local_tz


Current = Table(
    'current',
    meta,
    Column('city', String, primary_key=True),
    Column('country', String),
    Column("text", String),
    Column("temp_c", Float),
    Column("feels_c", Float),
    Column("temp_f", Float),
    Column("feels_f", Float),
    Column("humidity", String),
    Column("wind_kph", Float),
    Column("wind_mph", Float),
    Column("wind_dir", Float),
    Column('time_requested', DateTime(timezone=local_tz), default=datetime.now(local_tz)),
)

Alerts = Table(
    'alerts',
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
    Column("country", String),
    Column('city', ForeignKey('Current.city')),
    Column('time_requested', DateTime(timezone=local_tz), default=datetime.now(local_tz)),
)

Forecasts = Table(
    'forecasts',
        meta,
    Column("sunrise", DateTime(local_tz)),
    Column("sunset", DateTime(local_tz)),
    Column("moonrise", DateTime(local_tz)),
    Column("moonset", DateTime(local_tz)),
    Column("min_temp_c", Float),
    Column("max_temp_c", Float),
    Column("avg_temp_c", Float),
    Column("min_temp_f", Float),
    Column("max_temp_f", Float),
    Column("avg_temp_f", Float),
    Column("maxwind_kph", Float),
    Column("avgvis_km", Float),
    Column("maxwind_mph", Float),
    Column("avgvis_miles", Float),
    Column("daily_chance_of_rain", String),
    Column("daily_chance_of_snow", String),
    Column("daily_will_it_rain", String),
    Column("daily_will_it_snow", String),
    Column("country", String),
    Column('city', ForeignKey('Current.city')),
    Column('time_requested', DateTime(timezone=local_tz), default=datetime.now(local_tz)),
)

# ctrl + shift + u + 00b0 + ENTER


def create_table():
    try:
        base_logger.internal('Creating tasks table(s)')

        asyncio.run(create_tables())
        base_logger.internal('Task table created')

    except Exception as e:
        error_logger.exception(e)

create_table()