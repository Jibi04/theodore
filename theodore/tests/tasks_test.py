import click
import rich_click as click

from click_option_group import optgroup, RequiredMutuallyExclusiveOptionGroup
from dateparser import parse
from sqlalchemy.exc import SQLAlchemyError
from theodore.core.utils import user_error, get_task_table, user_success, user_warning
from theodore.core.logger_setup import error_logger, base_logger



@click.group()
@click.pass_context             
def tasks_test(ctx):
    """Manage to-dos"""


@tasks_test.command()
@click.argument('title', type=str)
@click.option('--tags',type=str, help='comma separated text')
@click.option('--status', type=click.Choice(['pending', 'in_progress', 'completed', 'not_completed']), help='task status')
@click.option('--due', type=str, help='task due-date format(yyyy-mm-dd H:M:S, next-week, tommorow, 9am monday)')
@click.option('--remind', is_flag=True, help='set reminder')
@click.pass_context
def new(ctx, title, tags, status, due, remind):
    """Create new task"""
    base_logger.internal('getting manager from task manager')
    manager = ctx.obj['manager']

    base_logger.internal('loading params')
    task = ctx.params

    try: 

        if due:
            base_logger.internal(f'parsing due date {due}')
            due = parse(due)
            if due is None:
                user_error("Invalid date format")
                return
        else:
            due = None

        base_logger.internal('creating new tasks ... waiting for response from manager')
        response = {"ok": True, "message": "new task created", "data": task} # manager.new_task(title=title, tags=tags, status=status, due_date=due)

        base_logger.internal('getting message from response')
        msg = response.get('message')


        if not response.get('ok'):
            base_logger.internal('Aborting got a False response from tasks Manager')
            user_error(msg)
            return
        
        base_logger.internal('getting newly created task object from manager')
        task = response.get('data')

        user_success(msg)
        base_logger.debug(f"new task created task-obj: {task}")


    except SQLAlchemyError as e:
        user_error(f"{type(e).__name__}: {e}")
        error_logger.exception(f"{type(e).__name__}: {e}") 
        return
    except Exception as e:
        user_error(f"{type(e).__name__}: {e}")
        error_logger.exception(f"{type(e).__name__}: {e}") 
        return 

    if remind:
        base_logger.internal('user wants a scheduler')
        base_logger.internal('creating scheduler ...')
        if not due:
            user_warning('Cannot set reminder without due date')
            due_date = click.input('Due date fmt - (yyy-mm-dd) q - quit(): ')

            if due_date.lower().strip() == 'q': 
                base_logger.internal('user opted to abort shedule creation')
                base_logger.info('Aborting scheduler')
                return
    return


@tasks_test.command()
@click.argument('--task-id')
@click.option('--title', type=str)
@click.option('--tags',type=str, help='comma separated text')
@click.option('--due', type=str, help='task due-date format(yyyy-mm-dd H:M:S, next-week, tommorow, 9am monday)')
@click.option('--status', type=click.Choice(['pending', 'in_progress', 'completed', 'not_completed']), help='task status')
@click.pass_context
def update(ctx, **kwargs):
    """Update task data id, title, tags, status, due date"""
    base_logger.internal('loading task manager')
    manager = ctx.obj['manager']
    
    base_logger.internal('updating args map')
    args_map = kwargs

    try:
        base_logger.internal('getting client confirmation for update')
        if not click.confirm('Are you sure you want to make this updates?', show_default=True, default=False):
            base_logger.internal('client aborted move')
            base_logger.info('Aborting move')
            return
        
        base_logger.internal('updating task ... waiting for response from manager')
        response = {"ok": True, "message": "task updated"} #manager.update_task(**args_map)

        base_logger.internal('getting message from response')
        msg = response.get('message')
        if not response.get('ok'):
            base_logger.internal('Aborting got a False response from tasks Manager')
            user_error(msg)
            return
        
        user_success(msg)
        return
    except Exception as e:
        user_error(f"{type(e).__name__}: {e}")
        error_logger.exception(f"{type(e).__name__}: {e}")
        return


@tasks_test.command()
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
    manager = ctx.obj['manager']

    base_logger.internal('updating task logger')
    args_map = kwargs
    args_map["deleted"] = deleted
    args_map["all"] = all

    try:
        base_logger.internal('getting task ... waiting for response from manager')
        response = {"ok": False, "message": "No tasks were found sorry"} # manager.get_tasks(**args_map)

        if not response.get('ok'):
            base_logger.internal('Aborting got a False response from task manager')
            base_logger.error(response.get('message'))
            return
        
        base_logger.internal('getting data from response')
        data = response.get('data')
        base_logger.internal('getting table from')
        table = get_task_table(data, deleted)
        base_logger.internal(f'table data created {table}')
        user_success(table) 
        return
    except Exception as e:
        user_error(f"{type(e).__name__}: {e}")
        error_logger.exception(f"{type(e).__name__}: {e}")
        return


@tasks_test.command()
@click.option('--keyword', '-kw', help='keyword to search for')
@click.pass_context
def search(ctx, keyword):
    """Search for keyword in tags and title"""
    base_logger.internal('getting manager from ctx obj')
    manager = ctx.obj['manager']
    try:
        base_logger.internal('getting results from keyword search {keyword} task ... waiting for response from manager')
        response = {"ok": "False", "message": "No tasks added yet" } # manager.search(keyword)

        base_logger.internal('getting message from response')
        msg = response.get('message')
        if not response.get('ok'):
            base_logger.internal('Aborting got a False response from tasks Manager')
            user_error(msg)
            return
        
        base_logger.internal('getting data from response')
        data = response.get('data')
        base_logger.internal('getting table instance to display data')
        table = get_task_table(data)

        user_success(table)
        return
    
    except Exception as e:
        user_error(f"{type(e).__name__}: {e}")
        error_logger.exception(f"{type(e).__name__} {e}")
        return


@tasks_test.command()
@optgroup.group('trash options', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--title', help='task title to delete')
@optgroup.option('--all', '-a', is_flag=True, help='move all tasks to trash')
@optgroup.option('--task_id', '-tid', type=int)
@optgroup.option('-ids', type=str, help='comma separated ids')
@click.pass_context
def trash(ctx, ids, **kwargs):
    """Move task(s) to trash"""

    base_logger.internal('loading tasks manager from ctx manager')
    manager = ctx.obj['manager']
    base_logger.debug(f'Task manager loaded {manager}')

    base_logger.internal('loading list ctx params')
    args_map = ctx.params
    base_logger.debug(f'Ctx params loaded {args_map}')

    if ids:
        ids = [int(tid) for tid in ids.split(',')]
        args_map['ids'] = ids

    try:
        base_logger.internal('confirming task move to trash')
        if not click.confirm(f'[warning]Are you sure you want to delete task?', default='n', show_default=True):
            base_logger.internal('client aborted move')
            base_logger.info('Aborting move')
            return

        base_logger.internal(f'moving to trash {args_map} ... waiting for response from manager')
        response = {"ok": True, "message": "Task(s) moved to trash"} # manager.move_trash(**args_map)

        base_logger.internal('getting message from response')
        msg = response.get('message', 'An unknown error occurred')
    except Exception as e:
        user_error(f"{type(e).__name__}: {e}")
        error_logger.exception(f"{type(e).__name__}: {e}")
        return
    
    if not response.get('ok'):
        base_logger.internal('Aborting got a False response from tasks Manager')

        user_error(msg)
        return
    
    user_success(msg)
    return


@tasks_test.command()
@optgroup.group('trash options', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--all', '-a', is_flag=True, help='permanently delete all tasks')
@optgroup.option('--title', help='task title to delete')
@optgroup.option('--task_id', '-tid', type=int)
@optgroup.option('-ids', type=str, help='comma separated ids')
@click.pass_context
def delete(ctx, ids, **kwargs):
    """Permanently delete task(s) from bin"""
    base_logger.internal('loading tasks manager from ctx obj')
    manager = ctx.obj['manager']
    
    args_map = ctx.params
    if ids:
        base_logger.internal('cleaning ids to ints')
        ids = [int(tid) for tid in ids.split(',')]
        args_map['ids'] = ids
        base_logger.debug(f'Ids cleaned successfully {ids}')

    try:
        base_logger.internal('getting user confirmation to permanently delete')
        if not click.confirm(f'[warning]Are you sure you want to delete task?:', default='n', show_default=True):
            base_logger.internal('client aborted move')
            base_logger.info('Aborting move')
            return
        
        base_logger.internal(f'deleting {args_map} ... waiting for response from manager')
        response = {"ok": True, "message": "Task(s) deleted"} # manager.delete(**args_map)
        msg = response.get('message', 'An unknown error occurred')
    except Exception as e: 
        user_error(f"{type(e).__name__}: {e}")
        error_logger.exception(f'{type(e).__name__}: {e}')
        return
    if not response.get('ok'):
        user_error(msg)
        return
    
    user_success(msg)
    return


@tasks_test.command()
@optgroup.group('trash options', cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--all', '-a', is_flag=True, help='restore all tasks')
@optgroup.option('--title', help='task title to restore')
@optgroup.option('--task_id', '-tid', type=int)
@optgroup.option('-ids', type=str, help='comma separated ids')
@click.pass_context
def restore(ctx, ids, **kwargs):
    """Restore task(s) from trash bin"""
    base_logger.internal('loading tasks manager from ctx obj')
    manager = ctx.obj['manager']
    
    args_map = ctx.params
    if ids:
        base_logger.internal('cleaning ids to ints')
        ids = [int(tid) for tid in ids.split(',')]
        args_map['ids'] = ids
        base_logger.debug(f'Ids cleaned successfully {ids}')

    try:
        base_logger.internal(f'restoring trash {args_map} ... waiting for response from manager')
        response = {"ok": False, "message": "sorry what has been done cannot be undone"} # manager.restore(**args_map)

        base_logger.internal('getting task response')
        msg = response.get('message', 'An unknown error occurred')
    except Exception as e:
        user_error(f"{type(e).__name__}: {e}")
        error_logger.exception(f"{type(e).__name__}: {e}")
        return
    if not response.get('ok'):
        user_error(msg)
        return
    
    user_success(msg)
    return