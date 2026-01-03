import click
import time
import rich_click as click
from click_option_group import optgroup, RequiredAllOptionGroup
from theodore.core.utils import base_logger, user_error
from theodore.core.theme import console


@click.group()
@click.pass_context
def file_manager(ctx):
    """Move, copy, delete and organize files and folders"""

@file_manager.command()
@optgroup.group(name='default args', cls=RequiredAllOptionGroup)
@optgroup.option('--name', '-f', help="Name of File to move")
@optgroup.option('--destination', '-d', help="Desired Location of file")
@click.option('--all', '-a', is_flag=True, help='Copy all files')
@click.option('--base_path', '-p', default="~/", help="Present Location of file, for easy access")
@click.option('--recursive', '-r', is_flag=True, help="Recursively search for file")
@click.pass_context
def move(ctx, name, destination, base_path, recursive, all):
    """Move files and folder(s) to destinations of your choice"""
    manager = ctx.obj['file_manager']
    # name, (dst, base) = manager.parse_user_regex_search(source, destination, base_path)
    if recursive:
        # start_time = time.perf_counter()
        # message = "Parsing through all the files in your PC this is gonna take a while"
        # stop_time = time.perf_counter()

        # if start_time - stop_time > 4:
        #     message = "You really have alot of files..."
        # console.status(status="")
        pass
    manager.move(src=name, dst=destination, recursive=recursive, base_path=base_path, all=all)
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
    manager.copy(src=source, dst_path=destination, recursive=recursive, base_path=base_path, all=all)
    return

@file_manager.command()
@click.option('--name', '-f', type=str, help='name of file or directory to delete', required=True)
@click.option('--all', '-a', is_flag=True, type=bool, help='delete all files in base path arg matching name arg')
@click.option('--base_path', '-p', default='~/', help='set path to search for file')
@click.option('--recursive', '-r', is_flag=True, default=False)
@click.pass_context
def delete(ctx, name, base_path, recursive, all):
    """Permanent delete files and folder(s). Cannot undo action"""
    base_logger.internal('')
    manager = ctx.obj['file_manager']
    manager.delete(pattern=name, base_path=base_path, recursive=recursive, all=all)
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
    return

@file_manager.command()
@click.option('--source-dir', default='/home/jibi/Downloads')
@click.pass_context
def organize(ctx, source_dir):
    """Automate files movements"""
    manager = ctx.obj['file_manager']
    manager.organize(source_dir)
    return


@file_manager.command()
@click.option('--dir-name', type=str, help='Name of directory to list', required=True)
@click.option('--dir-location', '-l', default='~/', help='path to search for Name set recursive if unsure')
@click.option('--recursive', '-r', is_flag=True, default=False)
@click.pass_context
def list(ctx, dir_name, dir_location, recursive):
    """Lists all contents of directory"""
    manager = ctx.obj['file_manager']
    contents = manager.view_folder(dir_name, dir_location, recursive)
    if not contents:
        user_error(f"There is no file named '{dir_name}' in '{dir_location}'")
        return 
    all_items = manager.get_location_content(location=contents[0], recursive=recursive)
    table, _ = manager.get_files_table(all_items)
    console.print(table)
    return