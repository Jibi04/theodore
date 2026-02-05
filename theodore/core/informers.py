"""
Docstring for theodore.core.informers

Calling UTILS imports so many large modules and just to inform a client is absurd.

"""

import traceback
from typing import Any
from datetime import datetime
from theodore.core.logger_setup import base_logger, error_logger


class LogsHandler:

    def format_error(self) -> str:
        return traceback.format_exc()

    def inform_error_logger(self, task_name, error_stack, reason, status: str = "Cancelled"):
        error_logger.internal(
                f"""
Task Name: {task_name}
status: {status}
Reason: {reason}
Error stack: {error_stack}
                """
            )

    def inform_base_logger(self, task_name: str, task_response: Any, status):
        base_logger.internal(
        f"""
Task Name: {task_name}
status: {status}
Task response: {task_response}
                """)
        
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