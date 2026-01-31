import rich_click as click
import asyncio

from dateparser import parse
from click_option_group import optgroup, RequiredMutuallyExclusiveOptionGroup, RequiredAllOptionGroup, RequiredAnyOptionGroup
from sqlalchemy.exc import SQLAlchemyError
from theodore.core.utils import user_error, get_task_table, user_success, normalize_ids
from theodore.core.theme import console
from theodore.core.logger_setup import error_logger
from theodore.cli.async_click import AsyncCommand
 


@click.group()
@click.pass_context             
def task_manager(ctx):
    """Manage to-dos"""


@task_manager.command()
@optgroup.group('required options', cls=RequiredAllOptionGroup)
@optgroup.option('--title', '-t', type=str)
@click.option('--description', '-d', type=str, help='comma separated text')
@click.option('--status', '-s', type=click.Choice(['pending', 'in_progress', 'completed', 'not_completed']), help='task status')
@click.option('--due', type=str, help='task due-date format(yyyy-mm-dd H:M:S, next-week, tommorow, 9am monday)')
@click.option('--remind', is_flag=True, help='set reminder')
@click.pass_context
def new(ctx, title, description, status, due, remind):
    """Create new task"""
    manager = ctx.obj['task_manager']
    args_map = ctx.params

    try: 

        if due:
            due = parse(due)
            if due is None:
                user_error("Invalid date format")
                return
        else:
            due = None
            
        args_map['due'] = due

        response = asyncio.run(manager.new_task(**args_map))

        msg = response.get('message')


        if not response.get('ok'):
            user_error(msg)
            return
        
        task = response.get('data')

        user_success(msg)

    except SQLAlchemyError as e:
        user_error(f"Database Error: {str(e)}") 
        return
    except Exception as e:
        user_error(f"{type(e).__name__}: {e}")
        return

    if remind:
        if not due:
            due_date = click.input('Due date fmt - (yyy-mm-dd) q - quit(): ')

            if due_date.lower().strip() == 'q': 
                return
    return


@task_manager.command()
@optgroup.group('requried any option', cls=RequiredAnyOptionGroup)
@optgroup.option('--title', '-t', type=str)
@optgroup.option('--task-id', '-tid', type=int)
@click.option('--tags',type=str, help='comma separated text')
@click.option('--due', type=str, help='task due-date format(yyyy-mm-dd H:M:S, next-week, tommorow, 9am monday)')
@click.option('--status', type=click.Choice(['pending', 'in_progress', 'completed', 'not_completed']), help='task status')
@click.pass_context
def update(ctx, **kwargs):
    """Update task data id, title, tags, status, due date"""
    manager = ctx.obj['task_manager']
    
    args_map = kwargs

    try:
        if not click.confirm('Are you sure you want to make this updates?', show_default=True, default=False):
            return
        response = asyncio.run(manager.update_task(**args_map))

        msg = response.get('message')
        if not response.get('ok'):
            user_error(msg)
            return
        
        user_success(msg)
        return
    except Exception as e:
        error_logger.exception(f"{type(e).__name__}: {e}")
        return


@task_manager.command(cls=AsyncCommand)
@optgroup.group('list options', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--all', '-a', is_flag=True, help='Get all tasks in')
@optgroup.option('--deleted', '-d', is_flag=True, help='List all deleted tasks')
@optgroup.option('-created-before', help='return list created before date')
@optgroup.option('-created-after', help='return task created after date')
@optgroup.option('-created-on', help='return tasks created on')
@optgroup.option('-due-before', help='return tasks due on')
@optgroup.option('-due-after', help='return tasks due on')
@optgroup.option('-due-on', help='return tasks created on')
@click.option('-filter-status', type=click.Choice(['in_progress', 'pending', 'completed', 'not_completed']), help='filter status list')
@click.pass_context
async def list(ctx, all, deleted, **kwargs):
    """List task(s) by filter"""
    
    manager = ctx.obj['task_manager']

    args_map = kwargs
    args_map["deleted"] = deleted
    args_map["all"] = all

    try:
        response = await manager.get_tasks(**args_map)

        if not response.get('ok'):
            user_error(response.get('message'))
            return
        
        data = response.get('data')
        table = get_task_table(data, deleted)
        console.print(table )
        return
    except Exception as e:
        user_error(f"{type(e).__name__}: {e}")
        return


@task_manager.command()
@click.option('--keyword', '-kw', help='keyword to search for')
@click.pass_context
def search(ctx, keyword):
    """Search for keyword in tags and title"""
    manager = ctx.obj['task_manager']
    try:
        response = asyncio.run(manager.search_tasks(keyword))

        msg = response.get('message')
        if not response.get('ok'):
            user_error(msg)
            return
        
        data = response.get('data')
        table = get_task_table(data)

        console.print(table)
        return
    
    except Exception as e:
        error_logger.exception(f"{type(e).__name__}: {e}")
        return


@task_manager.command()
@optgroup.group('trash options', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--title', '-t', help='task title to delete')
@optgroup.option('--all', '-a', is_flag=True, help='move all tasks to trash')
@optgroup.option('--task_id', '-tid', type=int)
@optgroup.option('-ids', type=str, help='comma separated ids')
@click.pass_context
def trash(ctx, ids, **kwargs):
    """Move task(s) to trash"""

    manager = ctx.obj['task_manager']

    args_map = ctx.params

    if ids:
        ids = normalize_ids(task_ids=ids)
        args_map['ids'] = ids

    try:
        if not click.confirm(f'[warning]Are you sure you want to delete task?', default='n', show_default=True):
            return
        response = asyncio.run(manager.move_to_trash(**args_map))

        msg = response.get('message', 'An unknown error occurred')
    except Exception as e:
        error_logger.exception(f"{type(e).__name__}: {e}")
        return
    
    if not response.get('ok'):
        user_error(msg)
        return
    
    user_success(msg)
    return


@task_manager.command()
@optgroup.group('trash options', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--all', '-a', is_flag=True, help='permanently delete all tasks')
@optgroup.option('--title', help='task title to delete')
@optgroup.option('--task_id', '-tid', type=int)
@optgroup.option('-ids', type=str, help='comma separated ids')
@click.pass_context
def delete(ctx, ids, **kwargs):
    """Permanently delete task(s) from bin"""
    manager = ctx.obj['task_manager']
    
    args_map = ctx.params
    if ids:
        ids = normalize_ids(task_ids=ids)
        args_map['ids'] = ids

    try:
        if not click.confirm(f'[warning]Are you sure you want to delete task?:', default='n', show_default=True):
            return
        response = asyncio.run(manager.delete_task(**args_map))
        msg = response.get('message', 'An unknown error occurred')
    except Exception as e:
        user_error(f"{type(e).__name__}: {e}")
        return
    
    if not response.get('ok'):
        user_error(msg)
        return
    
    user_success(msg)
    return


@task_manager.command()
@optgroup.group('trash options', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--all', '-a', is_flag=True, help='restore all tasks')
@optgroup.option('--title', help='task title to restore')
@optgroup.option('--task_id', '-tid', type=int)
@optgroup.option('-ids', type=str, help='comma separated ids')
@click.pass_context
def restore(ctx, ids, **kwargs):
    """Restore task(s) from trash bin"""
    manager = ctx.obj['task_manager']
    
    args_map = ctx.params
    if ids:
        ids = normalize_ids(task_ids=ids)
        args_map['ids'] = ids

    try:
        response = asyncio.run(manager.restore_from_trash(**args_map))

        msg = response.get('message', 'An unknown error occurred')
    except Exception as e:
        user_error(f"{type(e).__name__}: {e}")
        return
    
    if not response.get('ok'):
        user_error(msg)
        return
    
    user_success(msg)
    return
