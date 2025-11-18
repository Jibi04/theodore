from theodore.core.logger_setup import base_logger
from theodore.managers.configs_manager import Configs_manager
import requests
from pathlib import Path
from http.client import IncompleteRead
from requests.exceptions import HTTPError, ConnectionError, ChunkedEncodingError, ConnectTimeout, ReadTimeout
import time, sys, json
from datetime import datetime, timezone
from fake_user_agent import user_agent
from theodore.core.utils import send_message, user_success, user_error
import tempfile
import re
# Import tqdm for progress bar management
from tqdm.auto import tqdm

ua = user_agent()
manager = Configs_manager()


# set existence of file as markers for pause, resume or download
TEMP_DIR = Path(tempfile.gettempdir()) / "theodore_downloads"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# TEMP_DIR = Path(__file__).parent.parent / "theodore_temp"
# TEMP_DIR.mkdir(parents=True, exist_ok=True)

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
        movies['downloads']['movies'].setdefault(filename, {})

        movies['downloads']['movies'][filename].update(
            {
                "is_downloaded": True,
                "date_downloaded": datetime.now(timezone.utc).isoformat(),
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

        # ----------- Remove stale markers before starting or resuming download --------------

        for attempt in range(1, retries + 1):

            # pause_marker_path(filename).unlink(missing_ok=True)
            # cancel_marker_path(filename).unlink(missing_ok=True)

            # movies = manager.load_file(movie=True)

            for attempt in range(1, retries + 1):

                try:
                    base_logger.internal(f"Cleaning markers for: {filename}")
                    pause_marker_path(filename).unlink(missing_ok=True)
                    cancel_marker_path(filename).unlink(missing_ok=True)
                except Exception as e:
                    user_error(f"MARKER CLEAN ERROR: {e}")
                    raise

                try:
                    movies = manager.load_file(movie=True)
                except Exception as e:
                    print("LOAD FILE ERROR:", e)
                    raise

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
                    user_success(f'Attempt {attempt}/{retries}: starting request')
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

                            # 3. Initialize tqdm bar
                            # initial: start from the previously downloaded bytes (for resume)
                            # total: the total expected size
                            # desc: label for the bar (using filename)
                            # unit: bytes
                            # unit_scale: True for B, KB, MB, etc.
                            # disable: only disable if total_size is 0 (optional)
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
                                                return send_message(False, message=f'Download cancelled for {filename}')
                                            
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
                    err_msg = str(e)

                    if e.response.status_code == 416:
                        cls().update_client(filename=filename, movies=movies, filepath=filepath)
                        return
                    user_error(f"HTTP ERROR: ", err_msg)
                    time.sleep(30)
                    if attempt == retries:
                        user_error("Max retries reached. Aborting...")
                        return send_message(False, message=f"Http Error: {err_msg}")
                    continue
                except (IncompleteRead, ConnectionError, ReadTimeout, ChunkedEncodingError, ConnectTimeout) as e:
                    print()
                    user_error(f"{type(e).__name__}: {str(e)}")
                    print()
                    if attempt == retries:
                        user_error("Max retries reached, Aborting...")
                        return send_message(False, message=f'"error": {str(e)}')
                    for sec in range(5, 0, -1):
                        sys.stdout.write(f"\rRetrying in {sec} seconds...")
                        sys.stdout.flush()
                        time.sleep(1)
                    print()

                except Exception as e:
                    user_error(f"Unexpected error: {e}")
                    return send_message(False, message=f'"error": {str(e)}')

            return send_message(False, message="Download failed unexpectedly")


        



