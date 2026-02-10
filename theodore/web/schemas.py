from fastapi import Form
from pydantic import BaseModel, Field, model_validator
from typing import Annotated, Literal


class Job(BaseModel):
    key: str
    func_path: str | None = None
    trigger: Literal["interval", "cron"]
    hour: Annotated[int | None, Field(ge=0, le=23)] = None
    minute: Annotated[int | None, Field(ge=0, le=59)] = None
    second: Annotated[int | None, Field(ge=0, le=59)] = None
    day: Annotated[int | None, Field(ge=1, le=31)] = None
    dow: Annotated[int | None, Field(ge=0, le=6)] = None
    week: Annotated[int | None, Field(ge=1, le=53)] = None
    month: Annotated[int | None, Field(ge=1, le=12)] = None
    year: Annotated[int | None, Field(ge=2026, le=9999)] = None

    @model_validator(mode="before")
    @classmethod
    def validate_time(cls, data):
        keys = ['hour', 'minute', 'second', 'day', 'day_of_week', 'week', 'month', 'year']
        values = [data.get(key) for key in keys]

        if not any(values):
            raise ValueError("No Time set.")
        
        return data
    
    @classmethod
    def get_form(cls):

        func_path: str = Form(...)
        key: str = Form(...)
        trigger: Literal["interval", "cron"] = Form(...)
        hour: Annotated[int | None, Field(ge=0, le=23)] = Form(...)
        minute: Annotated[int | None, Field(ge=0, le=59)] = Form(...)
        second: Annotated[int | None, Field(ge=0, le=59)] = Form(...)
        day: Annotated[int | None, Field(ge=1, le=31)] = Form(...)
        dow: Annotated[int | None, Field(ge=0, le=6)] = Form(...)
        week: Annotated[int | None, Field(ge=1, le=53)] = Form(...)
        month: Annotated[int | None, Field(ge=1, le=12)] = Form(...)
        year: Annotated[int | None, Field(ge=2026, le=9999)] = Form(...)

        return cls(
            func_path=func_path,
            key=key,
            trigger=trigger,
            hour=hour,
            minute=minute,
            second=second,
            day=day,
            dow=dow,
            week=week,
            month=month,
            year=year
            )