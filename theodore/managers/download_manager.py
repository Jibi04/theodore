import asyncio, aiofiles
import httpx
import random
from theodore.core.logger_setup import base_logger
from theodore.managers.configs_manager import ConfigManager
from theodore.core.time_converters import  get_localzone
from theodore.core.informers import user_success, user_error, user_info
from theodore.core.db_operations import DBTasks
from theodore.models.downloads import DownloadTable
from datetime import datetime
from pathlib import Path
from tqdm.asyncio import tqdm

# --- Global Setup ---
ua = random.choice(
(
    "Mozilla/5.0 (X11; Linux x86_64) ",
    "AppleWebKit/537.36 (KHTML, like Gecko) ",
    "Chrome/121.0.0.0 Safari/537.36"
)
)

config_manager = ConfigManager()
db_manager = DBTasks(DownloadTable)

class DownloadManager:

    def __init__(self):
        self.active_events = {}
        self.cancel_flags = {}
        self._workers = asyncio.Semaphore(4)
        self._lock = asyncio.Lock()

    async def stop_download(self, filepath, filename) -> None:
        """Removes the downloading marker."""
        async with self._lock:
            try:
                self.cancel_flags[filename] = True
                if filepath.exists():
                    await aiofiles.os.remove(filepath)
            except KeyError:
                user_error(f"Cannot cancel '{filename}' Not downloading.")
            except asyncio.CancelledError:
                pass
            return
    
    async def pause(self, filename, **kwargs) -> None:
        async with self._lock:
            try:
                event: asyncio.Event = self.active_events[filename]
                event.clear()
            except KeyError:
                user_error(f"Cannot pause '{filename}' not currently downloading")
            except asyncio.CancelledError:
                pass
            return

    async def resume(self, filename, **kwargs) -> None:
        async with self._lock:
            try:
                event: asyncio.Event = self.active_events[filename]
                event.set()
            except KeyError:
                user_error(f"Cannot resume '{filename}' not among paused downloads")
            except asyncio.CancelledError:
                pass
            return
        
    async def update_status(self, filename: str, filepath: Path, total_size: int) -> None:
        """updates the database filesize percentage for querying download status"""
        async with self._lock:
            downloaded_percentage = round((filepath.stat().st_size / total_size) * 100, 1)
            await db_manager.upsert_features(
                values = {'download_percentage': downloaded_percentage,'filepath': str(filepath)}, 
                primary_key={'filename': filename}
            )
            return

    async def update_client(self, filename: str, filepath: Path) -> None:
        """Updates the database entry on successful download."""
        conditions = {'filename': filename}
        values = {"is_downloaded": True, "date_downloaded": datetime.now(get_localzone())}
        await db_manager.upsert_features(values=values, primary_key=conditions)
        user_success(f'{filename} download complete and database updated!')
        return

    async def download_file(self, url: str, directory: Path | str, filename: str | None=None, chunksize: int=8192, retries: int=10) -> None:
        async with self._workers:
            self.active_events[filename] = asyncio.Event()
            self.active_events[filename].set()

            base_logger.internal('Preparing file directory for download')
            filepath = Path(directory).expanduser()
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            if not filename:
                filename = filepath.name
            try:
                for attempt in range(1, retries + 1):
                    downloaded_bytes = 0
                    # -------- Resume feature: Check size before request ---------
                    if filepath.exists():
                        try:
                            # Pathlib stat is synchronous but acceptable for small metadata check
                            downloaded_bytes = filepath.stat().st_size
                        except OSError:
                            downloaded_bytes = 0
                    
                    # Range header for resuming
                    headers = {"Range": f"bytes={downloaded_bytes}-", "User-Agent": ua} 
                    # Mode: append ('ab') if resuming, write ('wb') if starting fresh (though 'ab' is safer)
                    mode = 'ab' 

                    async with httpx.AsyncClient(timeout=30) as client:
                        try:
                            user_success(f'Downloading {filename} Attempt {attempt}/{retries}: starting request...')
                            async with client.stream('GET', url=url, headers=headers) as response:
                                response.raise_for_status()
                                code = response.status_code
                                # --- Handle non-resumable download (Server returns 200 instead of 206) ---
                                if code == 200 and downloaded_bytes > 0:
                                    user_info("Server ignored Range header (200 OK). Starting download from scratch.")
                                    try:
                                        await aiofiles.os.remove(filepath)
                                    except FileNotFoundError:
                                        pass 
                                    downloaded_bytes = 0 
                                    # Continue to the next attempt, which will now start with a fresh file
                                    continue 
                                # --- TQDM SETUP START ---
                                # 1. Determine total size from headers
                                total_size = 0
                                content_range = response.headers.get('Content-Range')
                                content_length = response.headers.get('Content-Length', '0')
                                
                                if code == 206 and content_range:
                                    # Resume successful (206 Partial Content)
                                    expected_total = int(content_range.split('/')[-1])
                                    total_size = expected_total
                                elif code == 200:
                                    # New download (200 OK)
                                    total_size = int(content_length)
                                    
                                # Only proceed if we have a total size and haven't fully downloaded
                                if downloaded_bytes < total_size and total_size > 0:
                                    # Use aiofiles.open for asynchronous file handling
                                    async with aiofiles.open(filepath, mode=mode) as f:
                                        # Use tqdm for async progress bar
                                        with tqdm(
                                            initial=downloaded_bytes,
                                            total=total_size,        
                                            desc=f"Downloading {filename}",
                                            unit='B',
                                            unit_scale=True,
                                            disable=(total_size == 0)
                                        ) as t:

                                            # Iterate over bytes from the stream
                                            downloaded_chunk= 0
                                            async for chunk in response.aiter_bytes(chunk_size=chunksize):
                                                await self.active_events[filename].wait()
                                                if self.cancel_flags.get(filename, None):
                                                    user_info('Download Cancelled')
                                                    return
                                                # Write the chunk and update progress
                                                if chunk:
                                                    await f.write(chunk)
                                                    written_chunk = len(chunk)
                                                    t.update(written_chunk)
                                                    downloaded_chunk += written_chunk

                                                chunk_percentage = int((downloaded_chunk / total_size) * 100)
                                                if chunk_percentage > 5:
                                                    asyncio.create_task(self.update_status(filename, filepath, total_size))
                                                    downloaded_chunk = 0
                                                    
                                    # --- Integrity Check after file is fully streamed and closed ---
                                    final_size = filepath.stat().st_size
                                    if final_size != total_size:
                                        # Invalid file integrity. Re-starting download
                                        try:
                                            await aiofiles.os.remove(filepath)
                                        except FileNotFoundError:
                                            pass
                                        user_error(f"Download finished but file size mismatch: {final_size} != {total_size}. Restarting...")
                                        base_logger.internal("Corrupted file data restarting download")
                                        continue # Go to the next retry attempt
                                    else:
                                        # SUCCESS PATH
                                        user_success(f"Download complete for {filename}.")
                                        await self.update_client(filename=filename, filepath=filepath) 
                                        return
                        # --- Error Handling ---
                        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.ReadError, httpx.WriteError) as err:
                            user_error(f"{type(err).__name__} during download of {filename}. Attempting retry {attempt + 1}/{retries}...")
                            base_logger.internal("HTTPX timeout occurred.")
                            await asyncio.sleep(2 ** attempt)
                            continue
                        except httpx.HTTPStatusError as e:
                            status_code = e.response.status_code
                            if status_code == 403:
                                # Permanent forbidden error
                                condition = dict(filename=filename)
                                await db_manager.delete_features(and_conditions=condition)
                                user_error(f'Unable to download {filename}: link forbidden (403).')
                                return
                            elif status_code == 302:
                                user_error('URL moved to another Location, Check updated URL and try again.')
                                await self.stop_download(filename=filename, filepath=filepath)
                                await db_manager.delete_features(and_conditions={'filepath': str(filepath)})
                                user_info('Defunct file removed')
                                return
                            elif status_code == 416:
                                if filepath.exists() and filepath.stat().st_size == total_size: # Assuming total_size was set previously or correctly inferred
                                    user_success(f"File {filename} already fully downloaded (416 received).")
                                    await self.update_client(filename=filename, filepath=filepath)
                                    return
                                # If 416 but size is wrong, something went wrong, restart from 0
                                downloaded_bytes = 0
                                user_error("416 received but local file size mismatch, restarting.")
                                await aiofiles.os.remove(filepath)
                                continue # Restart loop
                            else:
                                user_error(f"HTTP error {e.response.status_code} for {filename}. Attempting retry {attempt + 1}/{retries}...")
                                base_logger.internal(f"HTTPX Status Error: {e.response.status_code}")
                            await asyncio.sleep(2 ** attempt * 3)
                            continue
                        except KeyboardInterrupt:
                            user_info('Keyboard Interupt Aborting...')
                            await asyncio.sleep(0.7)
                            self.active_events.clear()
                            self.cancel_flags.pop(filename, None)
                            return
                        except Exception as e:
                            user_error(f"An unexpected error occurred while downloading {filename}: {type(e).__name__} Stopping...")
                            await asyncio.sleep(1)
                            raise
            finally:
                self.active_events.pop(filename, None)
                self.cancel_flags.pop(filename, None)
        
            stmt = """SELECT 1 FROM download_manager WHERE filename = :filename AND is_downloaded = 0 LIMIT 1"""
            var_map = {'filename': filename}
            downloaded = await db_manager.run_query(stmt=stmt, sudo=True, var_map=var_map, one=True)
            if not downloaded.get('data'):
                user_error(f"An unexpected error occurred while downloading {filename}. Download Stopped.")