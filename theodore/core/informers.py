"""
Docstring for theodore.core.informers

Calling UTILS imports so many large modules and just to inform a client is absurd.

"""

from datetime import datetime
from typing import Any
from theodore.core.logger_setup import base_logger, error_logger



def user_success(msg: str):
    return base_logger.info(f'[success]{msg}')

def user_warning(msg: str):
    return base_logger.warning(f'[warning]{msg}')

def user_error(msg: str):
    return error_logger.error(f'[error]{msg}')

def user_info(msg: str):
    return base_logger.info(msg)

def send_message(ok, message: str | None =None, date: datetime | None=None, data: Any | None=None):
    return {'ok': ok, 'message': message, 'data': data, 'date': date}