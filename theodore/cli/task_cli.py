import click
import rich_click as click
from theodore.cli.async_click import AsyncCommand

from dateparser import parse
from click_option_group import optgroup, RequiredMutuallyExclusiveOptionGroup, RequiredAllOptionGroup, RequiredAnyOptionGroup
from sqlalchemy.exc import SQLAlchemyError
from theodore.core.utils import user_error, user_success, user_info, get_task_table, base_logger
from theodore.core.theme import console
from theodore.ai.dispatch import TASK_MANAGER
 


@click.group()
@click.pass_context             
def task_manager(ctx):
    """Manage to-dos"""
    ctx.obj['task_manager'] = TASK_MANAGER

@task_manager.command(cls=AsyncCommand)
@click.option('--title', '-t', type=str, help="task title", required=True)
@click.option('--description', '-d', type=str, help='comma separated text')
@click.option('--status', '-s', type=click.Choice(['pending', 'in_progress', 'completed', 'not_completed']), help='task status')
@click.option('--due', type=str, default=None, help='task due-date format(yyyy-mm-dd H:M:S, next-week, tommorow, 9am monday)')
@click.option('--remind', is_flag=True, help='set reminder')
@click.pass_context
async def new(ctx, **kwargs):
    """Create new task"""
    base_logger.internal('getting manager from task manager')
    manager = ctx.obj['task_manager']
    args_map = kwargs

    try: 
        due = args_map.get('due', None)
        if due is not None:
            due = parse(due)

        args_map['due'] = due

        args_map = {key: val for key, val in args_map.items() if val is not None}
        args_map.pop('remind')
        base_logger.internal('creating new tasks ... waiting for response from manager')
        response = await manager.new_task(**args_map)

        base_logger.internal('getting message from response')
        msg = response.get('message')


        if not response.get('ok'):
            user_error(msg)
            return
        
        base_logger.internal('getting newly created task object from manager')
        task = response.get('data')

        user_success(msg)
        base_logger.debug(f"new task created task-obj: {task}")
    except TypeError:
        user_error(f"Invalid Due date")
        return
    except SQLAlchemyError as e:
        base_logger.internal('A Database error occurred Aborting ...')
        user_error(f"Database Error: {e}") 
        return
    except Exception as e:
        base_logger.internal('An unknown error occurred Aborting ...')
        user_error(f"{type(e).__name__}: {e}")
        return

    # if remind:
    #     base_logger.internal('user wants a scheduler')
    #     base_logger.internal('creating scheduler ...')
    #     if not due:
    #         user_warning('Cannot set reminder without due date')
    #         due_date = click.input('Due date fmt - (yyy-mm-dd) q - quit(): ')

    #         if due_date.lower().strip() == 'q': 
    #             base_logger.internal('user opted to abort shedule creation')
    #             user_info('Aborting scheduler')
    #             return
    return


@task_manager.command(cls=AsyncCommand)
@optgroup.group('requried any option', cls=RequiredAnyOptionGroup)
@optgroup.option('--title', '-t', type=str)
@optgroup.option('--task-id', '-tid', type=int)
@click.option('--description', '-d',type=str, help='comma separated text')
@click.option('--status', type=click.Choice(['pending', 'in_progress', 'completed', 'not_completed']), help='task status')
@click.pass_context
async def update(ctx, **kwargs):
    """Update task data id, title, tags, status, due date"""
    base_logger.internal('loading task manager')
    manager = ctx.obj['task_manager']
    base_logger.internal('updating args map')
    args_map = {key: val for key, val in kwargs.items() if val if not None}

    try:
        base_logger.internal('getting client confirmation for update')
        if not click.confirm('Are you sure you want to make this updates?', show_default=True, default=False):
            base_logger.internal('client aborted move')
            user_info('Aborting move')
            ctx.abort()
        
        base_logger.internal('updating task ... waiting for response from manager')
        response = await manager.update_task(**args_map)

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


@task_manager.command(cls=AsyncCommand)
@optgroup.group('list filters', cls=RequiredMutuallyExclusiveOptionGroup)
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
    
    base_logger.internal('loading task manager')
    manager = ctx.obj['task_manager']

    base_logger.internal('updating task logger')
    args_map = kwargs
    args_map["deleted"] = deleted
    args_map["all"] = all

    try:
        base_logger.internal('getting task ... waiting for response from manager')
        response = await manager.get_tasks(**args_map)

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


@task_manager.command(cls=AsyncCommand)
@click.option('--keyword', '-kw', type=str, help='keyword to search for')
@click.pass_context
async def search(ctx, keyword):
    """Search for keyword in tags and title"""
    base_logger.internal('getting manager from ctx obj')
    manager = ctx.obj['task_manager']
    try:
        base_logger.internal('getting results from keyword search {keyword} task ... waiting for response from manager')
        response = await manager.search_tasks(keyword)
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


@task_manager.command(cls=AsyncCommand)
@optgroup.group('trash options', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--title', '-t', type=str, help='task title to delete')
@optgroup.option('--all', '-a', is_flag=True, type=bool, help='move all tasks to trash')
@optgroup.option('--task_id', '-tid', type=int)
@optgroup.option('-ids', type=str, help='comma separated ids')
@click.pass_context
async def trash(ctx, **kwargs):
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
        response = await manager.move_to_trash(**args_map)

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


@task_manager.command(cls=AsyncCommand)
@optgroup.group('trash options', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--all', '-a', is_flag=True, help='permanently delete all tasks')
@optgroup.option('--title', help='task title to delete')
@optgroup.option('--task_id', '-tid', type=int)
@optgroup.option('-ids', type=str, help='comma separated ids')
@click.pass_context
async def delete(ctx, **kwargs):
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
        response = await manager.delete_task(**args_map)
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


@task_manager.command(cls=AsyncCommand)
@optgroup.group('trash options', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--all', '-a', is_flag=True, help='restore all tasks')
@optgroup.option('--title', help='task title to restore')
@optgroup.option('--task_id', '-tid', type=int)
@optgroup.option('-ids', type=str, help='comma separated ids')
@click.pass_context
async def restore(ctx, ids, **kwargs):
    """Restore task(s) from trash bin"""
    base_logger.internal('loading tasks manager from ctx obj')
    manager = ctx.obj['task_manager']
    args_map = ctx.params
    try:
        response = await manager.restore_from_trash(**args_map)
        msg = response.get('message', 'An unknown error occurred')
    except Exception as e:
        user_error(f"{type(e).__name__}: {e}")
        return
    
    if not response.get('ok'):
        user_error(msg)
        return
    user_success(msg)
    return


