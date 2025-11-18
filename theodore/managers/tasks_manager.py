import  rich_click  as cl
from theodore.core.utils import send_message, parse_date, base_logger, user_error, normalize_ids
from theodore.core.theme import cli_defaults, console
import asyncio
from sqlalchemy import insert, update, delete, select
from sqlalchemy.exc import SQLAlchemyError
from theodore.models.base import engine
from datetime import datetime, timezone
from theodore.models.tasks import Tasks


cli_defaults()

class Task_manager():

    async def new_task(self, title: str = None, description: str = None, status: str = None, remind: str = None, due: datetime = None):
        try:
            async with engine.begin() as conn:
                if not title.strip():
                    return send_message(False, message='Invalid title cannot set null title')
                
                stmt = insert(Tasks).values(title=title, description=description, status=status, due=due)
                response = await conn.execute(stmt.returning(Tasks.c.task_id, Tasks.c.title))
                task_info = response.mappings().all()

                if not task_info:
                    base_logger.internal('Db returned a zero row count unable to create new task')
                    return send_message(False, "unable to create new task.")
                
                base_logger.debug(f'New task created: {task_info}')
                return send_message(True, message='New Task Created')
        except SQLAlchemyError as e:
            base_logger.internal('Database Error Aborting ...')
            user_error(f'SQLAlchemyError: {e}')
            return send_message(False, 'Task not updated')

        except Exception as e:
            base_logger.internal('An unknown error occurred Aborting ...')
            user_error(e)
            return send_message(False, message=f'{type(e).__name__}: {e}')


    async def update_task(self, task_id: int = None, title: str = None, description: str = None, status: str = None):
        update_values = {}
        base_logger.internal('Validating values to be updated')
        if title: update_values['title'] = title
        if description: update_values['description'] = description
        if status: update_values['status'] = status
        if not update_values:
            base_logger.internal('No values to update Aborting ...')
            return send_message(False, message='No values to update')
        
        base_logger.debug(f'Task updates to be updated {update_values}')
        try:
            base_logger.internal('Starting connection with database')
            async with engine.begin() as conn:
                base_logger.internal('Getting task objects from db to be updated')
                stmt = (update(Tasks)
                        .where(
                            (Tasks.c.task_id == task_id)&
                            (Tasks.c.is_deleted.is_(False))
                            )
                        .values(**update_values)
                        )
                base_logger.internal('Updating task data in db')
                response = await conn.execute(stmt.returning(Tasks.c.task_id, Tasks.c.title))
                rows = response.mappings().all()
                if not rows:
                    base_logger.internal('Db returned a zero row count no matching record found')
                    return send_message(False, "No matching record found.")
                base_logger.debug(f'tasks values {rows} updated')
            return send_message(True, message='Tasks updated.')
        except SQLAlchemyError as e:
            base_logger.internal('Database Error Aborting ...')
            user_error(f'SQLAlchemyError: {e}')
            return send_message(False, message='Task not updated')
        except Exception as e:
            base_logger.internal('An unknown error occurred Aborting ...')
            user_error(e)
            return send_message(False, message=f'{type(e).__name__}: {e}')


    async def delete_task(self, all: bool = False, title: str = None, task_id: int = None, ids: list = None) -> dict:
        base_logger.internal('Validating client arugments')
        task_ids = normalize_ids(task_id, ids)
        try:
            base_logger.internal('Starting connection with database')
            async with engine.begin() as conn:
                base_logger.internal('Preparing delete statement')
                stmt = delete(Tasks).where(Tasks.c.is_deleted.is_(True))
                msg = 'Task(s) deleted'
                if task_id or ids:
                    stmt = (stmt.where(
                                (Tasks.c.task_id.in_(task_ids))
                            ))
                    msg = f'deleted task(s) with ids: - {task_ids}'
                base_logger.internal('Executing delete statement')
                response = await conn.execute(stmt)
                if response.rowcount == 0:
                    base_logger.internal('Db returned a zero row count no matching record found')
                    return send_message(False, "No matching record found.")
                base_logger.debug(msg)
            return send_message(True, message='Task(s) deleted')
        except SQLAlchemyError as e:
            base_logger.internal('Database Error Aborting ...')
            user_error(f'SQLAlchemyError: {e}')
            return send_message(False, message='Task(s) not deleted')

        except Exception as e:
            base_logger.internal('An unknown error occurred Aborting ...')
            user_error(e)
            return send_message(False, message=f'{type(e).__name__}: {e}')


    async def move_to_trash(self, title: str = None, task_id: int = None, ids: list = None, all=False) -> dict:
        base_logger.internal('Validating client arugments')
        task_ids = normalize_ids(task_id, ids)
        try:
            base_logger.internal('Starting connection with database')
            async with engine.begin() as conn:
                base_logger.internal('Preparing move to trash statement')
                stmt = update(Tasks).where(Tasks.c.is_deleted.is_(False))
                msg = f'Trashed all tasks'
                if all:
                    stmt = (stmt.values(
                                is_deleted=True, 
                                date_deleted=datetime.now(timezone.utc))
                            )
                elif title:
                    stmt = (stmt.where(
                                Tasks.c.title.ilike(f'%{title}%')
                            ).values(
                                is_deleted=True, 
                                date_deleted=datetime.now(timezone.utc))
                            )
                    msg = f'Trashed Task with title {title}'
                else:
                    stmt = (stmt.where(
                                (Tasks.c.task_id.in_(task_ids))
                            ).values(
                                is_deleted=True, 
                                date_deleted=datetime.now(timezone.utc))
                            )
                    msg = f'Trashed task(s) with ids {task_ids}'
                base_logger.internal('Executing move to trash statement')
                response = await conn.execute(stmt)
                if response.rowcount == 0:
                    base_logger.internal('Db returned a zero row count no matching record found')
                    return send_message(False, message="No matching record found.")
                base_logger.debug(msg)
            return send_message(True, message='Task(s) moved to trash')
        except SQLAlchemyError as e:
            base_logger.internal('Database Error Aborting ...')
            user_error(f'SQLAlchemyError: {e}')
            return send_message(False, message='Task(s) not trashed')
        except Exception as e:
            base_logger.internal('An unknown error occurred Aborting ...')
            user_error(e)
            return send_message(False, message=f'{type(e).__name__}: {e}')
        

    async def restore_from_trash(self, task_id: int = None, ids: list = None, all=False) -> dict:
        base_logger.internal('Validating client arugments')
        task_ids = normalize_ids(task_id, ids)
        try:
            base_logger.internal('Starting connection with database')
            async with engine.begin() as conn:
                base_logger.internal('Preparing restore statement')
                stmt = update(Tasks).where(Tasks.c.is_deleted.is_(True))
                if all:
                    stmt = (stmt
                            .values(
                                is_deleted=False, 
                                date_deleted=datetime.now(timezone.utc)
                                )
                            )
                else:
                    stmt = (stmt.where(
                                (Tasks.c.task_id.in_(task_ids))
                            ).values(
                                is_deleted=False, 
                                date_deleted=datetime.now(timezone.utc)
                                )
                            )
                base_logger.internal('Executing restore statement')
                result = await conn.execute(stmt)
                if result.rowcount == 0:
                    base_logger.internal('Db returned a zero row count no matching record found')
                    return send_message(False, message='No matching record found')
                base_logger.debug(f'Moved task(s) with ids {task_ids} restored')
            return send_message(True, message='Task(s) restored')
        except SQLAlchemyError as e:
            base_logger.internal('Database Error Aborting ...')
            user_error(f'SQLAlchemyError: {e}')
            return send_message(False, message='Task(s) not restored')

        except Exception as e:
            base_logger.internal('An unknown error occurred Aborting ...')
            user_error(e)
            return send_message(False, message=f'{type(e).__name__}: {e}')


    async def search_tasks(self, keyword) -> dict: 
        try:
            async with engine.begin() as conn:
                base_logger.internal('Creating search statement')
                stmt = (select(Tasks)
                        .where(
                            (Tasks.c.title.ilike(f'%{keyword}%')) |
                            (Tasks.c.description.ilike(f'%{keyword}%'))
                            ))
                base_logger.internal('Executing search statement')
                result = await conn.execute(stmt)
                rows = result.fetchall()
                if not rows:
                    base_logger.internal('Db returned a zero row count no matching record found')
                    return send_message(False, message="No matching record found.")
                
                base_logger.internal('Converting db response objects into dictionary objects')
                rows_dict = [dict(row) for row in rows]
                base_logger.debug(f'Converted db response to dict objects {rows_dict}')

                return send_message(True, data=rows_dict)
        except SQLAlchemyError as e:
            base_logger.internal('Database Error Aborting ...')
            user_error(f'SQLAlchemyError: {e}')
            return send_message(False, message='Task(s) not restored')
        except Exception as e:
            base_logger.internal('An unknown error occurred Aborting ...')
            user_error(e)
            return send_message(False, message=f'{type(e).__name__}: {e}')


    async def get_tasks(self, task_id: int = None, ids: list = None, status: str = None, deleted=None, **date_args) -> dict:
        task_ids = normalize_ids(task_id, ids)
        try:
            async with engine.begin() as conn:
                base_logger.internal('Preparing list query')
                base_logger.internal('Applying list filters')
                if deleted:
                    query = select(Tasks).where(Tasks.c.is_deleted.is_(True))
                else:
                    query = select(Tasks).where(Tasks.c.is_deleted.is_(False))
                if task_ids: query = query.where(Tasks.c.task_id.in_(task_ids))
                if status in ("pending", "is_completed", "not_completed", "in_progress"):
                    query = query.where(Tasks.c.status == status)

                # Handle date filters
                base_logger.internal('Applying date filters')
                date_filters = {
                    "created_before": (date_args.get('created_before'), Tasks.c.date_created, '<'),
                    "created_after": (date_args.get('created_after'), Tasks.c.date_created, '>'),
                    "created_on": (date_args.get('created_on'), Tasks.c.date_created, '=='),
                    "due_before": (date_args.get('due_before'), Tasks.c.due, '<'),
                    "due_after": (date_args.get('due_after'), Tasks.c.due, '>'),
                    "due_on": (date_args.get('due_on'), Tasks.c.due, '==')
                }
                for filter_name, (date_value, column, operator) in date_filters.items():
                    if date_value:
                        parsed = parse_date(date_value)
                        if not parsed.get('ok'):
                            return send_message(False, message=f"Invalid date for {filter_name}: {parsed.get('message')}")
                        
                        parsed_date = parsed.get('date')
                        if operator == '<':
                            query = query.where(column < parsed_date)
                        elif operator == '>':
                            query = query.where(column > parsed_date)
                        else:  # ==
                            query = query.where(column == parsed_date)
                base_logger.internal('Executing list query ...')
                response = await conn.execute(query)
                base_logger.debug(f'Executed list query')

                base_logger.internal('Converting db response into dictionary objects')
                rows = response.mappings().all()
                if not rows:
                    base_logger.internal('Db returned a zero row count no matching record found')
                    return send_message(False, "No matching record found.")
                data = [dict(row) for row in rows]
                base_logger.debug(f'Converted db response to dict objects: {data}')
                return send_message(True, data=data)
        except SQLAlchemyError as e:
            base_logger.internal('Database Error Aborting ...')
            user_error(f'SQLAlchemyError: {e}')
            return send_message(False, 'Unable to process Database Error')
        except Exception as e:
            base_logger.internal('An unknown error occurred Aborting ...')
            user_error(e)
            return send_message(False, message=f'{type(e).__name__}: {e}')
        
