import rich_click as click
import traceback
import asyncio

from pydantic import ValidationError
from datetime import datetime
from tzlocal import get_localzone

from theodore.core.informers import user_info, user_error
from theodore.cli.async_click import AsyncCommand
from theodore.ai.dispatch import SHELL


@click.group()
def shell():
    """Perform custom, git and alembic commands."""
    pass

@shell.command(cls=AsyncCommand)
@click.option("--path", "-p", required=True)
@click.option("--drive", "-d", help="Rclone Drive name")
@click.option("--drive-env-key", "-env-key", help="Key to env variable for drive name")
@click.pass_context
async def backup(ctx, path, **kwds):
    """Backup files to cloud using rclone"""
    try:
        task = asyncio.create_task(SHELL.backup_files_rclone(directory=path, **kwds))
        user_info("Backup Initiated!")
        returncode = task.result()
        user_info(f"{path} backup") if returncode else user_error(f"{path} backup failed.")
    except (ValueError, ValidationError, asyncio.CancelledError):
        user_error(traceback.format_exc())

@shell.command(cls=AsyncCommand, name="custom-cmd")
@click.option("--cmd", "-c", required=True)
@click.pass_context
async def custom_cmd(ctx, cmd):
    """Perform custom shell commands."""
    try:
        returncode = await SHELL.custom_shell_cmd(custom_cmd=cmd)
        user_info(f"Success") if returncode else user_error(f"Custome cmd failed.")
    except (ValueError, ValidationError):
        user_error(traceback.format_exc())

@shell.command(cls=AsyncCommand, name="add-git")
@click.pass_context
async def add_git(ctx):
    """Stage git files for commit"""
    try:
        returncode = await SHELL.stage()
        user_info("Files Staged!") if returncode else user_error(f"File staging failed.")
    except (ValueError, ValidationError):
        user_error(traceback.format_exc())

@shell.command(cls=AsyncCommand, name="add-commit")
@click.option("--message", "-m", type=str, required=True)
async def add_commit(message):
    """Commit staged git files"""
    try:
        returncode = await SHELL.commit_git(message=message)
        cmt_msg = f"Files Committed\n Msg: {message}\nDate: {datetime.now(get_localzone())}"
        user_info(cmt_msg.partition("\n")[0]) if returncode else user_error(f"Commit failed.")
    except (ValueError):
        user_error(traceback.format_exc())


@shell.command(cls=AsyncCommand, name="migrate-db")
@click.option("--message", "-m", type=str, required=True)
async def migrate_db(message):
    """generate revision for database migration"""
    try:
        returncode = await SHELL.alembic_migrate(commit_message=message)
        user_info("Alembic Migration done.") if returncode else user_error(f"Alembic Migration failed.")
    except (ValueError):
        user_error(traceback.format_exc())

@shell.command(cls=AsyncCommand, name="upgrade-migration")
async def upgrade_migration():
    """Implement revision"""
    try:
        returncode = await SHELL.alembic_upgrade()
        user_info("Alembic upgrade done.") if returncode else user_error(f"Alembic upgrade failed.")
    except (ValueError):
        user_error(traceback.format_exc())


@shell.command(cls=AsyncCommand, name="upgrade-migration")
async def downgrade_migration():
    try:
        returncode = await SHELL.alembic_downgrade()
        user_info("Alembic downgrade done.") if returncode else user_error(f"Alembic downgrade failed.")
    except (ValueError):
        user_error(traceback.format_exc())