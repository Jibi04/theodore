import click
import rich_click as click
from click_option_group import optgroup, RequiredAllOptionGroup
from theodore.core.utils import base_logger
from theodore.core.theme import console


@click.group()
@click.pass_context
def file_manager(ctx):
    """Move, copy, delete and organize files and folders"""

@file_manager.command()
@optgroup.group(name='default args', cls=RequiredAllOptionGroup)
@optgroup.option('--source', '-f')
@optgroup.option('--destination', '-d')
@click.option('--all', '-a', is_flag=True, help='Copy all files')
@click.option('--base_path', '-p', default="~/")
@click.option('--recursive', '-r', is_flag=True)
@click.pass_context
def move(ctx, source, destination, base_path, recursive, all):
    """Move files and folder(s) to destinations of your choice"""
    manager = ctx.obj['file_manager']
    name, (dst, base) = manager.parse_user_regex_search(source, destination, base_path)
    manager.move(src=name, dst=dst, recursive=recursive, base_path=base, all=all)
    return

@file_manager.command()
@optgroup.group(name='default args', cls=RequiredAllOptionGroup)
@optgroup.option('--source', '-f')
@optgroup.option('--destination', '-d')
@click.option('--all', '-a', is_flag=True, help='Move all files')
@click.option('--base_path', '-p', default='~/')
@click.option('--recursive', '-r', is_flag=True)
@click.pass_context
def copy(ctx, source, destination, base_path, recursive, all):
    """copy files and folder(s) to destinations of your choice"""
    manager = ctx.obj['file_manager']

    name, (dst, base) = manager.parse_user_regex_search(source, destination, base_path)
    manager.copy(src=name, dst=dst, recursive=recursive, base_path=base, all=all)
    return

@file_manager.command()
@optgroup.group(name='default args', cls=RequiredAllOptionGroup)
@optgroup.option('--source', '-f')
@click.option('--all', '-a', is_flag=True)
@click.option('--base_path', '-p', default='~/', help='set path to search for file')
@click.option('--recursive', '-r', is_flag=True, default=False)
@click.pass_context
def delete(ctx, source, base_path, recursive, all):
    """Permanent delete files and folder(s). Cannot undo action"""
    base_logger.internal('')
    manager = ctx.obj['file_manager']
    name, path = manager.parse_user_regex_search(source, base_path)
    manager.delete(name, path[0], recursive, all)
    return

# @file_manager.command()
# @optgroup.group(name='default args', cls=RequiredAllOptionGroup)
# @optgroup.option('--source', '-s')
# @click.pass_context
# def archive(ctx, source):
#     """Archive file(s)"""

# @file_manager.command()
# @optgroup.group(name='default args', cls=RequiredAllOptionGroup)
# @optgroup.option('--source', '-s')
# @click.pass_context
# def extract(ctx, source):
    """extract file(s)"""

@file_manager.command()
@click.pass_context
def undo(ctx):
    """Undo most recent task"""
    manager = ctx.obj['file_manager']

    manager.undo_move()

@file_manager.command()
@click.option('--source-dir', default='/home/jibi/Downloads')
@click.pass_context
def organize(ctx, source_dir):
    """Automate files movements"""
    manager = ctx.obj['file_manager']
    manager.organize(source_dir)