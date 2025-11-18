import click
import rich_click as click
import asyncio
import re

from dateparser import parse
from pathlib import Path
from click_option_group import optgroup, RequiredMutuallyExclusiveOptionGroup, RequiredAllOptionGroup, RequiredAnyOptionGroup
from sqlalchemy.exc import SQLAlchemyError
from theodore.managers.file_manager import File_manager
from theodore.core.utils import user_error, user_success, user_warning, user_info, get_task_table, base_logger
from theodore.core.theme import console
 


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
    base_logger.internal('getting manager from task manager')
    manager = ctx.obj['task_manager']
    args_map = ctx.params

    try: 

        if due:
            base_logger.internal(f'parsing due date {due}')
            due = parse(due)
            if due is None:
                user_error("Invalid date format")
                return
        else:
            due = None
            
        args_map['due'] = due

        base_logger.internal('creating new tasks ... waiting for response from manager')
        response = asyncio.run(manager.new_task(**args_map))

        base_logger.internal('getting message from response')
        msg = response.get('message')


        if not response.get('ok'):
            user_error(msg)
            return
        
        base_logger.internal('getting newly created task object from manager')
        task = response.get('data')

        user_success(msg)
        base_logger.debug(f"new task created task-obj: {task}")


    except SQLAlchemyError as e:
        base_logger.internal('A Database error occurred Aborting ...')
        user_error(f"{type(e).__name__}: {e}") 
        return
    except Exception as e:
        base_logger.internal('An unknown error occurred Aborting ...')
        user_error(f"{type(e).__name__}: {e}")
        return

    if remind:
        base_logger.internal('user wants a scheduler')
        base_logger.internal('creating scheduler ...')
        if not due:
            user_warning('Cannot set reminder without due date')
            due_date = click.input('Due date fmt - (yyy-mm-dd) q - quit(): ')

            if due_date.lower().strip() == 'q': 
                base_logger.internal('user opted to abort shedule creation')
                user_info('Aborting scheduler')
                return
    return


@task_manager.command()
@optgroup.group('requried any option', cls=RequiredAnyOptionGroup)
@optgroup.option('--title', '-t', type=str)
@optgroup.option('--task-id', '-tid', type=int)
@click.option('--description', '-d',type=str, help='comma separated text')
# @click.option('--due', type=str, help='task due-date format(yyyy-mm-dd H:M:S, next-week, tommorow, 9am monday)')
@click.option('--status', type=click.Choice(['pending', 'in_progress', 'completed', 'not_completed']), help='task status')
@click.pass_context
def update(ctx, **kwargs):
    """Update task data id, title, tags, status, due date"""
    base_logger.internal('loading task manager')
    manager = ctx.obj['task_manager']
    
    base_logger.internal('updating args map')
    args_map = kwargs

    try:
        base_logger.internal('getting client confirmation for update')
        if not click.confirm('Are you sure you want to make this updates?', show_default=True, default=False):
            base_logger.internal('client aborted move')
            user_info('Aborting move')
            ctx.abort()
        
        base_logger.internal('updating task ... waiting for response from manager')
        response = asyncio.run(manager.update_task(**args_map))

        base_logger.internal('getting message from response')
        msg = response.get('message')
        if not response.get('ok'):
            user_error(msg)
            return
        
        user_success(msg)
        return
    except Exception as e:
        base_logger.internal('An unknown error occurred Aborting ...')
        user_error(f"{type(e).__name__}: {e}")
        return


@task_manager.command()
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
def list(ctx, all, deleted, **kwargs):
    """List task(s) by filter"""
    
    base_logger.internal('loading task manager')
    manager = ctx.obj['task_manager']

    base_logger.internal('updating task logger')
    args_map = kwargs
    args_map["deleted"] = deleted
    args_map["all"] = all

    try:
        base_logger.internal('getting task ... waiting for response from manager')
        response = asyncio.run(manager.get_tasks(**args_map))

        if not response.get('ok'):
            user_error(response.get('message'))
            return
        
        base_logger.internal('getting data from response')
        data = response.get('data')
        base_logger.internal('getting table from')
        table = get_task_table(data, deleted)
        base_logger.internal(f'table data created {table}')
        console.print(table )
        return
    except Exception as e:
        base_logger.internal('An unknown error occurred Aborting ...')
        user_error(f"{type(e).__name__}: {e}")
        return


@task_manager.command()
@click.option('--keyword', '-kw', help='keyword to search for')
@click.pass_context
def search(ctx, keyword):
    """Search for keyword in tags and title"""
    base_logger.internal('getting manager from ctx obj')
    manager = ctx.obj['task_manager']
    try:
        base_logger.internal('getting results from keyword search {keyword} task ... waiting for response from manager')
        response = asyncio.run(manager.search_tasks(keyword))
        base_logger.internal('getting message from response')
        msg = response.get('message')
        if not response.get('ok'):
            user_error(msg)
            return
        
        base_logger.internal('getting data from response')
        data = response.get('data')
        base_logger.internal('getting table instance to display data')
        table = get_task_table(data)
        user_success(table)
        return
    except Exception as e:
        base_logger.internal('An unknown error occurred Aborting ...')
        user_error(f"{type(e).__name__}: {e}")
        return


@task_manager.command()
@optgroup.group('trash options', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--title', '-t', help='task title to delete')
@optgroup.option('--all', '-a', is_flag=True, help='move all tasks to trash')
@optgroup.option('--task_id', '-tid', type=int)
@optgroup.option('-ids', type=str, help='comma separated ids')
@click.pass_context
def trash(ctx, **kwargs):
    """Move task(s) to trash"""

    base_logger.internal('loading tasks manager from ctx manager')
    manager = ctx.obj['task_manager']
    base_logger.debug(f'Task manager loaded {manager}')

    base_logger.internal('loading list ctx params')
    args_map = ctx.params
    base_logger.debug(f'Ctx params loaded {args_map}')
    try:
        base_logger.internal('confirming task move to trash')
        if not click.confirm(f'[warning]Are you sure you want to delete task?', default='n', show_default=True):
            base_logger.internal('client aborted move')
            user_info('Aborting move')
            ctx.abort()

        base_logger.internal(f'moving to trash {args_map} ... waiting for response from manager')
        response = asyncio.run(manager.move_to_trash(**args_map))

        base_logger.internal('getting message from response')
        msg = response.get('message', 'An unknown error occurred')
    except Exception as e:
        base_logger.internal('An unknown error occurred Aborting ...')
        user_error(f"{type(e).__name__}: {e}")
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
def delete(ctx, **kwargs):
    """Permanently delete task(s) from bin"""
    base_logger.internal('loading tasks manager from ctx obj')
    manager = ctx.obj['task_manager']
    args_map = ctx.params

    try:
        base_logger.internal('getting user confirmation to permanently delete')
        if not click.confirm(f'[warning]Are you sure you want to delete task?:', default='n', show_default=True):
            base_logger.internal('client aborted move')
            user_info('Aborting move')
            ctx.abort()
        
        base_logger.internal(f'deleting {args_map} ... waiting for response from manager')
        response = asyncio.run(manager.delete_task(**args_map))
        msg = response.get('message', 'An unknown error occurred')
    except Exception as e:
        base_logger.internal('An unknown error occurred Aborting ...')
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
    base_logger.internal('loading tasks manager from ctx obj')
    manager = ctx.obj['task_manager']
    args_map = ctx.params
    try:
        base_logger.internal(f'restoring trash {args_map} ... waiting for response from manager')
        response = asyncio.run(manager.restore_from_trash(**args_map))
        base_logger.internal('getting task response')
        msg = response.get('message', 'An unknown error occurred')
    except Exception as e:
        base_logger.internal('An unknown error occurred Aborting ...')
        user_error(f"{type(e).__name__}: {e}")
        return
    
    if not response.get('ok'):
        user_error(msg)
        return
    user_success(msg)
    return




@click.group()
@click.pass_context
def file_manager(ctx):
    """Move, copy, delete and organize files and folders"""


@file_manager.command()
@optgroup.group(name='default args', cls=RequiredAllOptionGroup)
@optgroup.option('--source', '-s')
@optgroup.option('--destination', '-d')
@click.pass_context
def move(ctx, source, destination):
    """Move files and folder(s) to destinations of your choice"""
    manager = ctx.obj['file_manager']
    


@file_manager.command()
@optgroup.group(name='default args', cls=RequiredAllOptionGroup)
@optgroup.option('--source', '-s')
@click.pass_context
def archive(ctx, source):
    """Archive file(s)"""


@file_manager.command()
@optgroup.group(name='default args', cls=RequiredAllOptionGroup)
@optgroup.option('--source', '-s')
@click.pass_context
def extract(ctx, source):
    """extract file(s)"""

@file_manager.command()
@optgroup.group(name='default args', cls=RequiredAllOptionGroup)
@optgroup.option('--source', '-s')
@optgroup.option('--destination', '-d')
@click.pass_context
def copy(ctx, source, destination):
    """copy files and folder(s) to destinations of your choice"""
    manager = ctx.obj['file_manager']


@file_manager.command()
@click.pass_context
def undo(ctx):
    """Undo most recent task"""
    manager = ctx.obj['file_manager']

    manager.undo_move()

@file_manager.command()
@optgroup.group(name='default args', cls=RequiredAllOptionGroup)
@optgroup.option('--source', '-f')
@click.option('--path', '-p', default='/home/jibi', help='set path to search for file')
@click.option('--recursive', '-r', is_flag=True, default=False)
@click.pass_context
def delete(ctx, source, path, recursive):
    """Move files and folder(s) to destinations of your choice"""
    base_logger.internal('')
    manager = ctx.obj['file_manager']

    base_logger.internal('cleaning client data for search')
    source = re.sub(r'[^ a-zA-z0-9]+', ' ', source)

    name = ".*".join(source.split(' '))

    base_logger.internal('creating base search path')
    base_path = Path(path).expanduser()

    base_logger.internal('getting confirmation from client for file deletion')
    if click.confirm('Are you sure you want to delete task?', show_default=True):
        manager.delete(name, base_path, recursive)
    return


@file_manager.command()
@click.option('--source-dir', default='/home/jibi/Downloads')
@click.pass_context
def organize(ctx, source_dir):
    """Automate files movements"""
    manager = ctx.obj['file_manager']

    manager.organize(source_dir)
