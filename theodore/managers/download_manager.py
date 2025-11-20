from theodore.core.logger_setup import base_logger
from theodore.managers.configs_manager import Configs_manager
import requests
from pathlib import Path
from http.client import IncompleteRead
from requests.exceptions import HTTPError, ConnectionError, ChunkedEncodingError, ConnectTimeout, ReadTimeout
import time, sys, json
from datetime import datetime, timezone
from fake_user_agent import user_agent
from theodore.core.utils import send_message, user_success, user_error, TEMP_DIR, local_tz
import re
from tqdm.auto import tqdm

ua = user_agent()
manager = Configs_manager()


def clean_file(filename) -> str:
    return re.sub(r'[^a-zA-Z0-9.-]', '_', filename)

def pause_marker_path(filename) -> Path:
    return TEMP_DIR / f"pause_{clean_file(filename)}.lock"

def cancel_marker_path(filename) -> Path:
    return TEMP_DIR / f"cancel_{clean_file(filename)}.lock"


class Downloads_manager:

    @classmethod
    def pause_download(cls, filename):
        base_logger.internal(f'Download logger initialized {filename}')
        pause_marker_path(filename).write_text("paused")
        return send_message(True, message="Pause marker created")

    @classmethod
    def cancel_download(cls, filename):
        cancel_marker_path(filename).write_text("cancelled")
        return send_message(True, message="marker created")
        

    @classmethod
    def resume_download(cls, filename):
        file = pause_marker_path(filename)
        if file.exists():
            file.unlink(missing_ok=True)
            return send_message(True, message="marker removed")
        
    def update_client(self, filename, movies:dict, filepath):
        movies.setdefault('downloads', {})
        movies['downloads'].setdefault('movies', {})
        movies['movies'].setdefault(filename, {})

        movies['downloads']['movies'][filename].update(
            {
                "is_downloaded": True,
                "timestamp": datetime.now(local_tz).isoformat(),
                "filepath": str(filepath)
                })
        
        user_success(f'{filename} download complete!')
        manager.save_file(movies, movie=True)

    @classmethod
    def download_movie(cls, url, filepath, filename=None, chunksize=8192, retries=10):

        filepath = Path(filepath).expanduser()
        base_logger.internal('Preparing file directory for download')
        filepath.parent.mkdir(parents=True, exist_ok=True)

        if not filename:
            filename = filepath.name

        try:
            movies = manager.load_file(movie=True)
        except Exception as e:
            user_error("LOAD FILE ERROR:", e)
            raise

        filedata = movies.get('downloads', {}).get('movies', {}).get(filename)
        if filedata and filedata.get('is_downloaded'):
            user_success(f'{filename} already downloaded')
            return send_message(False, message=f'{filename} already downloaded')
        
        for attempt in range(1, retries + 1):
            # ---- Remove stale markers before starting or resuming download ----
            try:
                base_logger.internal(f"Cleaning markers for: {filename}")
                pause_marker_path(filename).unlink(missing_ok=True)
                cancel_marker_path(filename).unlink(missing_ok=True)
            except Exception as e:
                user_error(f"MARKER CLEAN ERROR: {e}")
                return
            downloaded_bytes = 0

            # -------- Resume feature ---------
            if filepath.exists():
                try:
                    downloaded_bytes = filepath.stat().st_size
                except OSError:
                    downloaded_bytes = 0

            headers = {"Range": f"bytes={downloaded_bytes}-"} if downloaded_bytes > 0 else None
            mode = 'ab' if downloaded_bytes > 0 else 'wb'

            with requests.Session() as session:
                session.headers.update({"User-Agent": ua})
                try:
                    message = f'Downloading {filepath.stem} Attempt {attempt}/{retries}' \
                          if attempt < 2 else f'Attempt {attempt}/{retries}: restarting download'
                    user_success(message)
                    with session.get(url, stream=True, headers=headers, timeout=30) as r:
                        r.raise_for_status()
                        code = r.status_code

                        # if browser doesn't support resume start over
                        if code == 200 and downloaded_bytes > 0:
                            filepath.unlink(missing_ok=True)
                        
                        
                        # --- TQDM SETUP START ---
                        # 1. Determine total size from headers
                        content_range = r.headers.get('content-range')
                        if content_range:
                            expected_total = int(content_range.split('/')[-1])
                        else:
                            expected_total = int(r.headers.get('content-length', 0))
                        
                        # 2. Check if the file is incomplete
                        if downloaded_bytes < expected_total and expected_total > 0:
                            total_size = expected_total  # This is the total file size

                            with tqdm(
                                initial=downloaded_bytes,
                                total=total_size,
                                desc=f"Downloading {filepath.name}",
                                unit='B',
                                unit_scale=True,
                                disable=(total_size == 0)
                            ) as t:
                                
                                with open(filepath, mode) as f:
                                    for chunk in r.iter_content(chunk_size=chunksize):
                                        if chunk:
                                            pause_marker = pause_marker_path(filename)
                                            cancel_marker = cancel_marker_path(filename)

                                            # ------- pause / resume feature -------
                                            while pause_marker.exists():
                                                time.sleep(0.5)

                                            # ---------- Cancel feature ----------
                                            if cancel_marker.exists():
                                                user_error(f'Download cancelled for {filename}')
                                                return
                                            
                                            f.write(chunk)
                                            # 4. Use t.update() to advance the progress bar
                                            t.update(len(chunk))
        
                            # --- TQDM SETUP END ---
                        
                            # After the inner 'with tqdm(..)' block, we check the final size
                            final_size = filepath.stat().st_size

                            if final_size != total_size:
                                # Invalid file integrity Re-starting download
                                filepath.unlink(missing_ok=True)
                                user_error(f"Download finished but file size mismatch: {final_size} != {total_size}")
                                base_logger.internal("Corrupted file data restarting download")
                            else:
                                cls().update_client(filename=filename, movies=movies, filepath=filepath)
                                return
                    
                except HTTPError as e:
                    if attempt == retries:
                        user_error("Max retries reached. Aborting...")
                        user_error(f"Http Error: {err_msg}")
                        return
                    code = e.response.status_code
                    if code == 403:
                        user_error(f'{filename} URL Forbidden')
                        if movies.get('downloads', {}).get('movies', {}).get(filename, None):
                            movies["downloads"]["movies"].pop(filename)
                            manager.save_file(movies, movie=True)
                        return
                    err_msg = f"{type(e).__name__}: {filename} restarting download"
                    if code == 416:
                        cls().update_client(filename=filename, movies=movies, filepath=filepath)
                        break
                    user_error(err_msg)
                    time.sleep(30)
                    continue

                except (IncompleteRead, ConnectionError, ReadTimeout, ChunkedEncodingError, ConnectTimeout) as e:
                    print()
                    if attempt == retries:
                        user_error("Max retries reached, Aborting...")
                        return
                    user_error(f"{type(e).__name__}: {filename} restarting download")
                    print()
                    for sec in range(5, 0, -1):
                        sys.stdout.write(f"\rRetrying in {sec} seconds...")
                        sys.stdout.flush()
                        time.sleep(1)
                    print()

                except Exception as e:
                    user_error(f'"error": {str(e)}')
                    return

        user_error("Download failed unexpectedly")
        return


        



