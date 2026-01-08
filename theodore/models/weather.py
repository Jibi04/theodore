from datetime import datetime
from sqlalchemy import Table, Column, String, Float, Integer, ForeignKey, DateTime
from theodore.models.base import meta
from theodore.core.utils import local_tz


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
    Column("country", String, primary_key=True),
    Column('headline', String),
    Column('event', String),
    Column('city', ForeignKey('current.city')),
    Column('certainty', String),
    Column('urgency', String),
    Column('severity', String),
    Column('note', String),
    Column('effective', String),
    Column('description', String),
    Column('instructions', String),
    Column('time_requested', DateTime(timezone=local_tz), default=datetime.now(local_tz)),
)

Forecasts = Table(
    'forecasts',
    meta,
    Column("country", String, primary_key=True),
    Column('time_requested', DateTime(timezone=local_tz), default=datetime.now(local_tz)),
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
    Column("daily_chance_of_rain", Float),
    Column("daily_chance_of_snow", Float),
    Column("daily_will_it_rain", Integer),
    Column("daily_will_it_snow", Integer),
    Column('city', ForeignKey('current.city')),
)

# ctrl + shift + u + 00b0 + ENTER


