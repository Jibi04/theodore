from typing import Any
from pathlib import Path
import rich_click as click
from functools import lru_cache
from click_option_group import RequiredMutuallyExclusiveOptionGroup, optgroup

from theodore.core.lazy import get_db_handler
from theodore.cli.async_click import AsyncCommand
from theodore.core.transporter import send_command
from theodore.core.informers import user_error, user_info

@lru_cache
def get_downloader():
    from theodore.models.downloads import DownloadTable
    from theodore.core.db_operations import Downloads
    return Downloads(DownloadTable)


# ------------------------------------------
#             Main Downloads CLI 
# ------------------------------------------


async def resolve_file(filename):
    fullname = await get_full_name(filename)
    if not fullname:
        return None
    return await get_file_obj(filename=fullname)

async def inform_client(response: dict | None = None, message: str = "") -> None:
    response = response or {}
    _message = response.get('message', None) or message
    if response.get('ok', None) in (False, None):
        user_error(_message)
        return
    user_info(_message)
    return

async def get_full_name(filename):
    return await get_downloader().get_full_name(filename)   

async def get_file_obj(**kwargs) -> Any :
    return await get_db_handler().get_features(and_conditions=kwargs, first=True)

@click.group()
@click.option('--dir_path', '-p', default="~/Downloads", type=str, help='directory to save file in')
@click.pass_context
def downloads(ctx: click.Context, dir_path: str) -> None:
    """Download, Manage and track downloads"""
    # Group logic runs before subcommands.
    ctx.ensure_object(dict)
    ctx.obj['dir_path'] = Path(dir_path).expanduser()
    ctx.obj['downloader'] = get_downloader()

@downloads.command(cls=AsyncCommand, name="file")
@click.option('--url', '-u', type=str, help='comma separated urls', required=True)
@click.pass_context
async def file_(ctx: click.Context, url: str) -> None:
    """Download Files from Any where with simply a url, Web Scraper integration comming soon!"""
    downloader = ctx.obj['downloader']

    pending_downloads = await downloader.get_undownloaded_urls()

    urls_to_download = []
    urls = [u.strip() for u in url.split(',') if u.strip()]
    if not urls:
        await inform_client(message="No valid Urls to download")
        return
    
    urls_to_download.extend([downloader.parse_url(url) for url in urls])

    try:
        # bulk insert
        entries_to_insert = [url_map for url_map in urls_to_download if url_map.get('url') not in pending_downloads]
        if entries_to_insert:
            await downloader.bulk_insert(entries_to_insert)
        # -------------------------------------------------------------
        # 3. Queue Tasks and Database Insertion
        # -------------------------------------------------------------
        msg = await send_command(intent="DOWNLOAD", file_args=urls_to_download)
        user_info(msg)
    finally:
        pass

@downloads.command(cls=AsyncCommand)
@click.argument('filename', type=str)
@click.pass_context
async def cancel(ctx: click.Context, filename: str):
    """Cancel file download"""
    data = await resolve_file(filename=filename)
    if not data:
        await inform_client(message=f"No currently downloading file with name {filename}")
        return
    msg = await send_command(
        intent="CANCEL", 
        file_args={
            "filename": data.filename,
            "filepath": data.filepath
            }
        )
    user_info(msg)

@downloads.command(cls=AsyncCommand)
@click.argument('filename')
@click.pass_context
async def pause(ctx: click.Context, filename: str):
    """Pause File download"""
    data = await resolve_file(filename=filename)
    if not data:
        await inform_client(message=f"No currently downloading file with name {filename}")
        return
    msg = await send_command(
        intent="PAUSE", 
        file_args={
            "filename": data.filename, 
            "filepath": data.filepath
            }
        )
    user_info(msg)

@downloads.command(cls=AsyncCommand)
@optgroup.group(name="required field", cls=RequiredMutuallyExclusiveOptionGroup)
@optgroup.option('--filename', '-f', type=str, help="resume on download with filename")
@optgroup.option('--all', '-a', is_flag=True, help="Resume all downloads")
@click.pass_context
async def resume(ctx: click.Context, filename: str, all):
    """Resume Paused downloads"""
    downloader = ctx.obj['downloader']
    if not all:
        data = await resolve_file(filename=filename)
        if not data:
            await inform_client(message=f"No currently downloading file with name {filename}")
            return
        msg = await send_command(
            intent="RESUME", 
            file_args={
                "filename": data.filename, 
                "filepath": data.filepath
                }
            )
        user_info(msg)
        return 
        
    resumable_downloads = await downloader.get_undownloaded_urls()
    if not resumable_downloads:
        await inform_client(message="There are no pending downloads to continue.")
        return
    url_info = [ downloader.parse_url(url) for url in resumable_downloads ]
    msg = await send_command(intent="DOWNLOAD", file_args=url_info)
    user_info(msg)

@downloads.command(cls=AsyncCommand)
@click.argument('filename')
@click.pass_context
async def status(ctx, filename):
    """Get file download status of you file"""
    data = await resolve_file(filename)
    if not data:
        await inform_client(message=f'Could not find data with filename \'{filename}\' name not in downloads or too vague')   
        return
    status_text = "Completed" if data.is_downloaded else "In Progress/Paused"
    name = data.filename if len(data.filename) <= 30 else data.filename[:30] + '...'
    _percentage = data.download_percentage

    percentage = "Completed" if data.is_downloaded else _percentage or "jj0" + "% done!" 
    user_info(f"[File: {name}  | Status: {status_text} | Path: {data.filepath} | Downloaded size: {percentage}]")

if __name__ == "__main__":
    downloads()