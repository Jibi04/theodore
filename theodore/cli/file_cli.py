import click
import rich_click as click
from click_option_group import optgroup, RequiredAllOptionGroup
from theodore.core.theme import console
from theodore.managers.file_manager import FileManager


@click.group()
@click.pass_context
def file_manager(ctx):
    """Move, copy, delete and organize files and folders"""
    ctx.obj['file_manager'] = FileManager()


@file_manager.command()
@optgroup.group(name='default args', cls=RequiredAllOptionGroup)
@optgroup.option('--name', '-f', help="Name of File to move")
@optgroup.option('--destination', '-d', help="Desired Location of file")
@click.option('--all', '-a', is_flag=True, help='Move all files')
@click.pass_context
def move(ctx, name, destination, all):
    """Move files and folder(s) to destinations of your choice"""
    manager: FileManager = ctx.obj['file_manager']
    
    manager.move_file(src=name, dst=destination, all=all)
    return

@file_manager.command()
@optgroup.group(name='default args', cls=RequiredAllOptionGroup)
@optgroup.option('--name', '-f', help="Name of File to copy")
@optgroup.option('--destination', '-d', help="Desired Location of file")
@click.option('--all', '-a', is_flag=True, help='Copy all files')
@click.pass_context
def copy(ctx, name, destination, all):
    """Move files and folder(s) to destinations of your choice"""
    manager: FileManager = ctx.obj['file_manager']
    
    manager.copy_file(src=name, dst=destination, all=all)
    return

@file_manager.command()
@click.option('--name', '-f', type=str, help='name of file or directory to delete', required=True)
@click.option('--all', '-a', is_flag=True, type=bool, help='delete all files in base path arg matching name arg')
@click.pass_context
def delete(ctx, name, all):
    """Permanent delete files and folder(s). Cannot undo action"""
    manager: FileManager = ctx.obj['file_manager']
    manager.delete_file(src=name, all=all)
    return

@file_manager.command()
@click.pass_context
def undo(ctx):
    """Undo most recent task"""
    manager: FileManager = ctx.obj['file_manager']
    manager.undo_move()
    return

@file_manager.command()
@click.option('--source-dir', default=".", required=True)
@click.pass_context
def organize(ctx, source_dir):
    """Automate file Movement, source directory defaults to current directory."""
    manager: FileManager = ctx.obj['file_manager']
    manager.organize_files(src=source_dir)
    return


@file_manager.command()
@click.option('--dir-name', '-d', type=str, help='Name of directory to list', required=True)
@click.pass_context
def list(ctx, dir_name):
    """Lists all contents of directory"""
    manager: FileManager = ctx.obj['file_manager']

    files = manager.list_all_files(target_dir=dir_name)

    table, _ = manager.get_files_table(files)
    console.print(table)
    return