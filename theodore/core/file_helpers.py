import re
import getpass
import json
import shutil
import tarfile
import time
import traceback
import threading
import concurrent.futures

from datetime import datetime
from itertools import chain
from pathlib import Path
from tzlocal import get_localzone
from typing import Tuple, Dict, Generator, List, Any, Iterable

from theodore.core.logger_setup import base_logger, error_logger
from theodore.core.paths import JSON_DIR
from theodore.core.informers import user_error

HOME = Path.home()
DOWNLOADS = HOME/"Downloads"
VIDEOS = HOME/"Videos"
DOCUMENTS = HOME/"Documents"
GAURD = threading.Lock()
FILE_LOGS = JSON_DIR/"file_entries.log"

dst_map = {
    '.deb': HOME / DOCUMENTS / "deb_files",
    '.sh': HOME / DOCUMENTS / "sh_files",
    '.mkv': HOME / VIDEOS / "newly_downloaded",
    '.mp4': HOME / VIDEOS / "newly_downloaded",
    '.pdf': HOME / DOCUMENTS / 'pdf_files',
    '.docx': HOME / DOCUMENTS / 'docx_files',
    '.tar': HOME / DOCUMENTS / 'tar_files',
    '.zip': HOME / DOCUMENTS / 'zip_files',
    '.csv': HOME / "scripts/theodore/theodore/data/datasets/uncleaned_csv_files",
    '.xlsx': HOME / DOCUMENTS/ 'excel_files',
    "unknown": HOME/"unknown_downloads"
}

def validate_source(src: str | Path)-> None:
    if not Path(src).expanduser().exists():
        raise FileNotFoundError(f"File not found '{src}'.")


def get_file_logs() -> Dict:
    with GAURD:
        if FILE_LOGS.exists():
            try:
                return json.loads(FILE_LOGS.read_text())
            except json.JSONDecodeError:
                FILE_LOGS.unlink()
        return {}


def save_file_logs(logs: dict):
    with GAURD:
        logger = Path(FILE_LOGS)
        if isinstance(logs, dict):
            logger.write_text(json.dumps(logs, indent=4))
            return
        logger.write_text(json.dumps({}))


def resolve_entry(
        *,
        src: str | Path, 
        dst: str | Path
    ) -> Tuple[str, str]:
    
    validate_source(src)
    abs_dst = Path(dst).expanduser().absolute()
    abs_dst.mkdir(parents=True, exist_ok=True)
    
    abs_src = resolve_path(src)

    if not Path(f"{abs_dst}/{abs_src.name}").exists():
        return str(abs_src), f"{abs_dst}/{abs_src.name}"

    basename = abs_src.name
    curr_time = int(time.time())
    new_dst_path = f"{abs_dst}/{curr_time}-{basename}"

    return str(abs_src), new_dst_path


def resolve_path(path):
    return Path(path).expanduser().absolute()


def iterate_path(pattern: Generator):
    return chain.from_iterable(pattern)


def log_entry(src: str, dst: str) -> None:
    entry = {
        "src": src,
        "dst": dst,
        "timestamp": time.time(),
        "user": getpass.getuser()
    }

    date = datetime.now(get_localzone()).isoformat()
    file_logs = get_file_logs()
    file_logs[date] = entry
    save_file_logs(file_logs)


def move_entry(
        *,
        src: Path | str, 
        dst: Path | str,
        log: bool = True
    ) -> None:
    """Move files and directories from one path to another"""
    src_str, dst_str =  resolve_entry(src=src, dst=dst)
    shutil.move(src=src_str, dst=dst_str)
    if log:
        log_entry(src=src_str, dst=dst_str)

def move_unknown_destination(
        src: str | Path
):
    validate_source(src)
    entry = resolve_path(src)

    key = entry.suffix
    destination = dst_map.get(key) or dst_map['unknown']
    move_entry(src=src, dst=destination)

    return destination, resolve_path(src)


def undo() -> None:
    logger = get_file_logs()
    _, last_task = logger.popitem()

    dst = Path(last_task.get('src')).parent
    src = Path(last_task.get('dst'))

    move_entry(src=src, dst=dst, log=False)
    save_file_logs(logger)


def copy_entry(
        *,
        src: Path | str,
        dst: Path | str,
        log: bool = True
) -> None:
    """Copy files files and directories from one path to another"""
    src_str, dst_str =  resolve_entry(src=src, dst=dst)
    shutil.copy(src=src_str, dst=dst_str)
    if log:
        log_entry(src=src_str, dst=dst_str)


def delete_entry(src: str | Path, dst: str | Path | None = None) -> None:
    validate_source(src=src)
    path = resolve_path(src)
    
    if path.is_file(): path.unlink(missing_ok=True)
    if path.is_dir(): shutil.rmtree(str(path))


def organize(src_path: str | Path) -> None:
    validate_source(src=src_path)

    for path in list(iter_dir_content(path=src_path, recursive=True)):
        if not path.is_file():
            continue

        dst = dst_map.get(path.suffix) or dst_map['unknown']
        dst.expanduser().mkdir(parents=True, exist_ok=True)

        move_entry(src=path, dst=dst)
        base_logger.internal(f"\nMoved {path.name} from {path.parent} to {dst.as_posix()}.")


def archive_folder(src: str | Path, filename: str | None = None, format: str = ".tar.gz"):
    if not (path:=resolve_path(src)).exists():
        raise ValueError(f"Path {src} could not be resolved.")
    
    name = (filename or path.stem) + format
    try:
        with tarfile.open(name, 'w') as tar:
            tar_info = tar.gettarinfo(path)

            if path.is_dir(): tar.add(path)
            elif path.is_file(): tar.addfile(tarinfo=tar_info)
            base_logger.internal(tar_info)
            return 1
    except tarfile.CompressionError:
        error_logger.info(traceback.format_exc())
        return 0

def extract_folder(src: str | Path, filename: str):
    if not (path:=resolve_path(src)).exists():
        raise ValueError(f"Path {path} could not be resolved.")
    try:
        with tarfile.open(filename, 'r') as tar:
            tar_info = tar.gettarinfo(path)
            tar.extractall(path)
            base_logger.internal(tar_info)
            return 1
    except tarfile.ReadError:
        error_logger.info(traceback.format_exc())
        return 0


def clean_user_search(name: str | Path) -> str:
    name = re.sub(r'[^_a-zA-z0-9/]+', ' ', str(name))
    return name.replace(' ', '.*?')


def iter_dir_content(path: Path | str, recursive: bool = False):
    """Get items in location"""
    _path = resolve_path(path)
    if not _path.exists():
        raise FileNotFoundError(f"'{path}' non existent!")
    
    if recursive:
        return _path.rglob('*')
    
    return _path.glob('*')


def search_with_match(entry_name: str, base_path: Path | str = "~", recursive = False) -> List[Path]:
    validate_source(src=str(base_path))
    path = resolve_path(base_path)
    
    match = list()
    for p in iter_dir_content(path=path, recursive=recursive):
        if re.search(entry_name, p.name):
            match.append(p)
    return match


def run_tasks(func: Any, args: List[Any] | set[Any], max_worker: int = 8) -> int:
    """Performs multiples tasks concurrently using the threadpool executor and map function."""
    if not isinstance(args, Iterable):
        raise TypeError(f"Concurrent Worker Expected an Iterable but got {type(args).__name__}")
    
    results = concurrent.futures.ThreadPoolExecutor(max_workers=max_worker).map(func, args)
    return sum(1 for result in results if result)


def bulk_run(func: Any, dst: Path | str, records: Dict[Any, Any], indices: List[Any] | None = None):
    if not isinstance(records, dict):
        # Invalid format
        return 0
    
    dest = resolve_path(dst).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    _args = indices or records.keys()

    def run(i):
        f = records.get(i)
        if not f:
            user_error(f"Invalid id {i}")
            return 0
        func(src=f, dst=dest)
        return 1
    
    return run_tasks(func=run, args=_args)