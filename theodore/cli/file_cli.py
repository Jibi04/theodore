import traceback
import rich_click as click

from theodore.core.theme import console
from theodore.core.informers import user_error, user_info
from click_option_group import optgroup, RequiredAllOptionGroup
from theodore.core.lazy import get_file_manager, get_dispatch
from theodore.core.file_helpers import archive_folder, extract_folder, resolve_path



@click.group()
@click.pass_context
def file_manager(ctx: click.Context):
    """Move, copy, delete and organize files and folders"""
    ctx.ensure_object(dict)



@file_manager.command()
@optgroup.group(name='default args', cls=RequiredAllOptionGroup)
@optgroup.option('--name', '-f', help="Name of File to move")
@optgroup.option('--destination', '-d', help="Desired Location of file")
@click.option('--all', '-a', is_flag=True, help='Move all files')
@click.pass_context
def move(ctx: click.Context, name, destination, all):
    """Move files and folder(s) to destinations of your choice"""
    manager = get_file_manager()
    DISPATCH = get_dispatch()
    DISPATCH.dispatch_cli(func=manager.move_file, src=name, dst=destination, all=all)
    return

@file_manager.command()
@optgroup.group(name='default args', cls=RequiredAllOptionGroup)
@optgroup.option('--name', '-f', help="Name of File to copy")
@optgroup.option('--destination', '-d', help="Desired Location of file")
@click.option('--all', '-a', is_flag=True, help='Copy all files')
@click.pass_context
def copy(ctx: click.Context, name, destination, all):
    """Move files and folder(s) to destinations of your choice"""
    manager = get_file_manager()
    DISPATCH = get_dispatch()
    DISPATCH.dispatch_cli(manager.copy_file, src=name, dst=destination, all=all)
    return

@file_manager.command()
@click.option('--name', '-f', type=str, help='name of file or directory to delete', required=True)
@click.option('--all', '-a', is_flag=True, type=bool, help='delete all files in base path arg matching name arg')
@click.pass_context
def delete(ctx: click.Context, name, all):
    """Permanent delete files and folder(s). Cannot undo action"""
    manager = get_file_manager()
    DISPATCH = get_dispatch()
    DISPATCH.dispatch_cli(manager.delete_file, src=name, all=all)
    return

@file_manager.command()
@click.pass_context
def undo(ctx: click.Context):
    """Undo most recent task"""
    manager = get_file_manager()
    manager.undo_move()
    return

@file_manager.command()
@click.option('--source-dir', "-d", default=".", required=True)
@click.pass_context
def organize(ctx: click.Context, source_dir):
    """Automate file Movement, source directory defaults to current directory."""
    manager = get_file_manager()
    DISPATCH = get_dispatch()
    DISPATCH.dispatch_cli(manager.organize_files, src=source_dir)
    return

@file_manager.command()
@click.option('--directory', '-d', type=str, help='Name of directory to list', required=True)
@click.pass_context
def list(ctx: click.Context, dir_name):
    """Lists all contents of directory"""
    manager = get_file_manager()
    DISPATCH = get_dispatch()
    files = DISPATCH.dispatch_cli(manager.list_all_files,target_dir=dir_name)

    table, _ = manager.get_files_table(files)
    console.print(table)
    return

@file_manager.command()
@click.option("--directory", "-p", required=True)
@click.option("--filename", "-n")
@click.option("--format", type=click.Choice([".xz", ".gz", ".gz2", ".zst"]), default=".xz")
@click.pass_context
def compress(ctx: click.Context, directory, filename, format):
    """Compress Files / Folders"""
    if not (path := resolve_path(directory)).exists():
        user_error(f"Path {directory} could not be resolved.")
        return
    name = filename or path.stem
    returncode = archive_folder(src=path, filename=name, format=".tar"+format)
    user_info(f"{name} compressed") if returncode else user_error(f"{name} compression failed.")

@file_manager.command()
@click.option("--directory", "-p", required=True)
@click.option("--filename", "-n")
@click.pass_context
def extract(ctx: click.Context, directory, filename):
    """Extract Files / Folders"""
    if not (path := resolve_path(directory)).exists():
        user_error(f"Path {directory} could not be resolved.")
        return
    name = filename or path.stem
    try:
        returncode = extract_folder(src=path, filename=name)
    except OSError:
        user_error(traceback.format_exc())
        return
    user_info(f"{name} extracted") if returncode else user_error(f"{name} extraction failed.")

