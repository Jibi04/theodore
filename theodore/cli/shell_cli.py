import traceback
import rich_click as click

from datetime import datetime
from tzlocal import get_localzone

from theodore.cli.async_click import AsyncCommand
from theodore.core.informers import user_info, user_error
from theodore.core.lazy import get_shell_manager, Asyncio, PydValidationError as ValidationError

@click.group()
@click.pass_context
def shell(ctx: click.Context):
    """Perform custom, git and alembic commands."""
    ctx.ensure_object(dict)
    ctx.obj['manager'] = get_shell_manager()
    ctx.obj['asyncio'] = Asyncio()

@shell.command(cls=AsyncCommand)
@click.option("--path", "-p", required=True)
@click.option("--drive", "-d", help="Rclone Drive name")
@click.option("--drive-env-key", "-env-key", help="Key to env variable for drive name")
@click.pass_context
async def backup(ctx: click.Context, path, **kwds):
    """Backup files to cloud using rclone"""
    SHELL = ctx.obj['manager']
    asyncio = ctx.obj['asyncio']
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
async def custom_cmd(ctx: click.Context, cmd):
    """Perform custom shell commands."""
    SHELL = ctx.obj['manager']
    try:
        returncode = await SHELL.custom_shell_cmd(custom_cmd=cmd)
        user_info(f"Success") if returncode else user_error(f"Custome cmd failed.")
    except (ValueError):
        user_error(traceback.format_exc())

@shell.command(cls=AsyncCommand, name="add")
@click.pass_context
async def add_git(ctx: click.Context):
    """Stage git files for commit"""
    SHELL = ctx.obj['manager']
    try:
        returncode = await SHELL.stage()
        user_info("Files Staged!") if returncode else user_error(f"File staging failed.")
    except (ValueError, ValidationError):
        user_error(traceback.format_exc())

@shell.command(cls=AsyncCommand, name="commit")
@click.option("--message", "-m", type=str, required=True)
@click.pass_context
async def commit(ctx: click.Context, message):
    """Commit staged git files"""
    SHELL = ctx.obj['manager']
    try:
        returncode = await SHELL.commit_git(message=message)
        cmt_msg = f"Files Committed\n Msg: {message}\nDate: {datetime.now(get_localzone())}"
        user_info(cmt_msg.partition("\n")[0]) if returncode else user_error(f"Commit failed.")
    except (ValueError):
        user_error(traceback.format_exc())


@shell.command(cls=AsyncCommand, name="migrate-db")
@click.option("--message", "-m", type=str, required=True)
@click.pass_context
async def migrate_db(ctx: click.Context, message):
    """generate revision for database migration"""
    SHELL = ctx.obj['manager']
    try:
        returncode = await SHELL.alembic_migrate(commit_message=message)
        user_info("Alembic Migration done.") if returncode else user_error(f"Alembic Migration failed.")
    except (ValueError):
        user_error(traceback.format_exc())

@shell.command(cls=AsyncCommand, name="upgrade-migration")
@click.pass_context
async def upgrade_migration(ctx: click.Context):
    """Implement revision"""
    SHELL = ctx.obj['manager']
    try:
        returncode = await SHELL.alembic_upgrade()
        user_info("Alembic upgrade done.") if returncode else user_error(f"Alembic upgrade failed.")
    except (ValueError):
        user_error(traceback.format_exc())


@shell.command(cls=AsyncCommand, name="upgrade-migration")
@click.pass_context
async def downgrade_migration(ctx: click.Context):
    SHELL = ctx.obj['manager']
    try:
        returncode = await SHELL.alembic_downgrade()
        user_info("Alembic downgrade done.") if returncode else user_error(f"Alembic downgrade failed.")
    except (ValueError):
        user_error(traceback.format_exc())

if __name__ == "__main__":
    shell()