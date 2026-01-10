import asyncio
import json
import rich_click as click
from theodore.models.downloads import file_downloader
from theodore.managers.download_manager import Downloads_manager
from theodore.managers.daemon_manager import Worker
from theodore.core.utils import user_success, Downloads, user_error, user_info, DB_tasks
from theodore.cli.async_click import AsyncCommand
from pathlib import Path

downloader = Downloads(file_downloader)
manager = Downloads_manager()
worker = Worker()

# ------------------------------------------
#             Main Downloads CLI 
# ------------------------------------------

@click.group()
@click.option('--dir_path', '-p', default="~/Downloads", type=str, help='directory to save file in')
@click.pass_context
def downloads(ctx: click.Context, dir_path: str) -> None:
    """Download, Manage and track downloads"""
    # Group logic runs before subcommands.
    ctx.obj['dir_path'] = Path(dir_path).expanduser()

@downloads.command(cls=AsyncCommand)
@click.option('--url', '-u', type=str, help='comma separated urls')
@click.option('--resume', is_flag=True, help='Resume specific file download')
@click.option('--dir_path', '-p', default="~/Downloads", type=str, help='directory to save file in')
@click.pass_context
async def file(ctx: click.Context, url: str, resume: bool, dir_path: Path) -> None:
    """Download, Manage and track downloads"""
    urls_to_download = []

    resumable_downloads = await downloader.get_undownloaded_urls()
    urls_to_download.extend([downloader.parse_url(url, dir_path) for url in resumable_downloads])
    if url:
        urls = [u.strip() for u in url.split(',') if u.strip()]
        if not urls:
            user_error("No valid URLs provided.")
            return
        urls_to_download.extend([downloader.parse_url(url, dir_path) for url in urls])

    if not url and not resume:
        user_info('No URLs provided and --resume not set.')
        return
    
    if not urls_to_download and resume:
        user_info('No unfinished downloads to resume.')
        return
    response = "Before start"
    try:
        
        # bulk insert
        entries_to_insert = [url_map for url_map in urls_to_download if url_map.get('url') not in resumable_downloads]
        if entries_to_insert:
            await downloader.bulk_insert(file_downloader, entries_to_insert)
        # -------------------------------------------------------------
        # 3. Queue Tasks and Database Insertion
        # -------------------------------------------------------------
        mail_data = {"cmd": "DOWNLOAD"}
        mail_data["file_args"] = urls_to_download

        json_str: str = json.encoder.JSONEncoder().encode(mail_data)
        response = await worker.send_signal(message=json_str.encode())
        user_info(response)
    finally:
        pass

@downloads.command(cls=AsyncCommand)
@click.argument('filename', type=str)
@click.pass_context
async def cancel(ctx: click.Context, filename: str):
    """Cancel file download"""

    _filename = await downloader.get_full_name(filename)
    if not filename:
        click.echo(f'Error: No record found for file matching "{filename}".')
        return
    with DB_tasks(file_downloader) as db_manager:
        file_obj = await db_manager.get_features(and_conditions={'filename': _filename}, first=True)
        if not file_obj:
            click.echo(f'Error: No record found for file matching "{filename}".')
            return
        mail_data = {
            "cmd": "CANCEL",
            "file_args": [{"filename": _filename, "filepath": file_obj.filepath}]
            }
        
        mail_data: str = json.encoder.JSONEncoder().encode(mail_data)
        await worker.send_signal(mail_data.encode())


@downloads.command(cls=AsyncCommand)
@click.argument('filename')
@click.pass_context
async def pause(ctx: click.Context, filename: str):
    """Pause File download"""
    _filename = await downloader.get_full_name(filename)
    if not filename:
        click.echo(f'Error: No record found for file matching "{filename}".')
        return
    with DB_tasks(file_downloader) as db_manager:
        file_obj = await db_manager.get_features(and_conditions={'filename': _filename}, first=True)
        if not file_obj:
            click.echo(f'Error: No record found for file matching "{filename}".')
            return
        mail_data = {
            "cmd": "PAUSE",
            "file_args": [{"filename": _filename, "filepath": file_obj.filepath}]
            }
        
        mail_data: str = json.encoder.JSONEncoder().encode(mail_data)
        await worker.send_signal(mail_data.encode())

@downloads.command(cls=AsyncCommand)
@click.argument('filename')
@click.pass_context
async def resume(ctx: click.Context, filename: str):
    """Resume Paused downloads"""
    _filename = await downloader.get_full_name(filename)
    if not file:
        click.echo(f'Error: No record found for file matching "{filename}".')
        return
    with DB_tasks(file_downloader) as db_manager:
        file_obj = await db_manager.get_features(and_conditions={'filename': _filename}, first=True)
        if not file_obj:
            click.echo(f'Error: No record found for file matching "{filename}".')
            return
        mail_data = {
            "cmd": "RESUME",
            "file_args": [{"filename": _filename, "filepath": file_obj.filepath}]
            }
        
        mail_data: str = json.encoder.JSONEncoder().encode(mail_data)
        await worker.send_signal(mail_data.encode())


@downloads.command(cls=AsyncCommand)
@click.argument('filename')
@click.pass_context
async def status(ctx, filename):
    """Get file download status of you file"""
    _filename = await downloader.get_full_name(filename)
    if _filename:
        with DB_tasks(file_downloader) as db_manager:
            f = await db_manager.get_features(and_conditions={'filename': _filename}, first=True)
            if f:
                status_text = "Completed" if f.is_downloaded else "In Progress/Paused"
                name = f.filename if len(f.filename) <= 30 else f.filename[:30] + '...'

                user_info(f"[File: {name}  | Status: {status_text} | Path: {f.filepath} | Downloaded size: {f.download_percentage}% done]")
    else:
        user_info(f'Could not find data with filename \'{filename}\' name not in downloads or too vague')
