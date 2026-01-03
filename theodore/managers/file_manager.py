import itertools as it
from pathlib import Path, PosixPath
from concurrent.futures import ThreadPoolExecutor
import shutil
import subprocess
import datetime
import json
import re
from typing import Dict, Iterable, List
from theodore.core.utils import user_success, user_error, JSON_DIR, TEMP_DIR, local_tz, normalize_ids, send_message, user_info
from rich.table import Table
from theodore.core.theme import console
from theodore.core.logger_setup import base_logger
from theodore.core.transporter import Communication_Channel

HOME = Path.home()
Downloads = HOME / "Downloads"
Videos = HOME / "Videos"
Documents = HOME / "Documents"

LOG_FILE = JSON_DIR /  "file_manager_logs.json"

channel = Communication_Channel()

target_dirs = {
    'peaky-blinders': HOME / Videos / 'Peaky Blinders' / "S3" 
}

EXTENSION_MAP = {
    '.deb': HOME / Documents / "Deb Files",
    '.sh': HOME / Documents / "SH Files",
    '.mkv': HOME / Videos,
    '.mp4': HOME / Videos,
    '.pdf': HOME / Documents / 'PDF Files',
    '.docx': HOME / Documents / 'DOCX Files',
    '.tar': HOME / Documents / 'Tar Files',
    '.zip': HOME / Documents / 'Zip Files',
    '.csv': HOME / Documents / 'CSV Files',
    '.xlsx': HOME / Documents / 'Excel Files'
}

pattern = ['*.mkv', '*.mp4', '*.deb', '*.sh', '*.pdf', '*.docx', '*.tar', '*.zip', '*.csv', '*.xlsx', '*.srt', '*.html'] 

class File_manager:
    def get_location_content_with_match(self, item_name: str, dir_location: Path | str, recursive) -> list[PosixPath]:
        """Search for file/dir in location"""
        locations = []
        location = Path(dir_location).expanduser()

        if not location.exists():
            user_error(f"location {dir_location} not found")
        if recursive:
            for path in location.rglob("**/*"):
                if re.search(item_name, path.name, re.I):
                    locations.append(path)
        else:
            for path in location.glob("*"):
                if re.search(item_name, path.name, re.I):
                    locations.append(path)
        return locations
    
    def clean_user_search(self, name: str) -> str:
            name = re.sub(r'[^ a-zA-z0-9]+', ' ', name)
            return name.replace(' ', '.*?')
    
    def get_client_response(self, items_list: Iterable, msg1: str= None, msg2: str = None) -> List | str:
        """Returns user id choices"""
        user_ids = []
        msg_prompt = msg1
        if len(items_list) > 1:
            msg_prompt = msg2
        res = console.input(f'[warning]{msg_prompt}[/warning]').lower().strip()
        if res in ('a', 'all'):
            return res
        user_ids = normalize_ids(task_ids=res)
        return user_ids

    
    def get_location_content(self, location: Path, recursive: bool = False) -> list[PosixPath]:
            """Get items in location"""
            if not location.exists():
                raise TypeError(f"Expected a Path object got {type(location)}")
            if recursive:
                return [item for item in location.rglob('*/**')]
            return [item for item in location.iterdir()]
    
    def view_folder(self, directory_name: str | Path, directory_location, recursive) -> list[PosixPath]:
        path = Path(directory_name).expanduser()
        args = tuple()
        if path.exists():
            args = (path, directory_location, recursive)
        else:
            cleaned_name = self.clean_user_search(directory_name)
            args = (cleaned_name, directory_location, recursive)
        return self.get_location_content_with_match(*args)
            
    def log_move(self, src: Path, dst: Path):
        entry = {
            "From": str(src),
            "To": str(dst),
            "timestamp": datetime.datetime.now(local_tz).isoformat()
        }
        old = []
        if LOG_FILE.exists():       
            try:    
                old = json.loads(LOG_FILE.read_text())
            except json.JSONDecodeError:
                pass
        old.append(entry)
        LOG_FILE.write_text(json.dumps(old, indent=2))
        return

    def delete(self, pattern, base_path, recursive, all):
        try:
            cleaned_name = self.clean_user_search(pattern)
            locations = self.get_location_content_with_match(cleaned_name, base_path, recursive)
            if not locations:
                user_info(f'File matching \'{pattern}\' Not Found.')
                return
            table, items_dict = self.get_files_table(locations)
            ids_to_delete = []
            if all:
                res = console.input("Are you sure you want to delete all files? [yes -(y) /no -(n)]")
                if res.lower() not in ('yes', 'y'):
                    return
                ids_to_delete.extend(items_dict.keys())
            else:
                msg1 = 'You are about to delete the file above confirm by passing the id of the file: '
                msg2 = f'More than one file matched \'{pattern}\' choose file(s) by id(s) to delete (q) to cancel, (a/all) for all matches: '
                msg = msg1
                if len(items_dict) > 1:
                    msg = msg2
                res = channel.make_request(prompt=msg, table=table)
                if not res:
                    return 
                elif res in ('a', 'all'):
                    ids_to_delete.extend(items_dict.keys())
                else:
                    selected_ids = normalize_ids(task_ids=res)
                    ids_to_delete.extend(selected_ids)
            def delete_file(i):
                try:
                    item = items_dict.get(i)
                    if not item:
                        user_error(f"Provided Invalid id {i}")
                        return
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(str(item))
                    return True
                except (OSError, IOError) as exc:
                    raise
            results = ThreadPoolExecutor(max_workers=8).map(delete_file, ids_to_delete)
            success_count = sum(1 for result in results if result)
            user_success(f'{success_count} file(s) to deleted')
            return
        except Exception as exc:
            user_error(str(exc))
            return

    def move(self, src: Path | str, dst: Path | str, recursive: bool, base_path, all) -> None:
        try:
            # ------------ soure
            src_name = self.clean_user_search(src)
            src_path = self.get_location_content_with_match(item_name=src_name, dir_location=base_path, recursive=recursive)
            # ------------ destination 
            dst_path = Path(dst).expanduser()
            if not src_path:
                user_info(f'File matching \'{src}\' Not Found.')
                return
            table, items_dict = self.get_files_table(src_path)
            ids_to_move = []
            if all:
                res = channel.make_request(prompt="[warning]Are you sure you want to move all files? [yes -(y) /no -(n)]: ")
                if res.lower() not in ('yes', 'y'):
                    return
                ids_to_move.extend(items_dict.keys())
            else:
                msg1 = f'You are about to move the file(s) above to {dst_path.name} confirm by passing the id of the file: '
                msg2 = f'More than one file matched \'{src}\' choose file(s) by id(s) to Move (q) to cancel, (a/all) for all matches: '
                msg = msg1
                if len(items_dict) > 1:
                    msg = msg2
                res = channel.make_request(prompt=msg, table=table)
                if not res:
                    return 
                elif res in ('a', 'all'):
                    ids_to_move.extend(items_dict.keys())
                else:
                    selected_ids = normalize_ids(task_ids=res)
                    ids_to_move.extend(selected_ids)

            def move_file(i):
                try:
                    f = items_dict.get(i)
                    if not f:
                        user_error(f"Provided Invalid id {i}")
                        return
                    dst_path.mkdir(parents=True, exist_ok=True)
                    new_path = dst_path / f.name
                    if new_path.exists():
                        res = channel.make_request(f'{f.name} already exists in {dst_path.name} O-overwrite Q-cancel: ')
                        if res.lower() in ('q', 'cancel'):
                            return 
                    shutil.move(str(f), str(new_path))
                    self.log_move(f, new_path)
                    return True
                except (IOError, OSError):
                    raise

            results = ThreadPoolExecutor(max_workers=8).map(move_file, ids_to_move)
            success_count = sum(1 for result in results if result)
            user_success(f'Moved {success_count} file(s) to {dst_path.name}.')
            return
        except Exception as exc:
            raise

    def copy(self, src: Path | str, dst_path: Path | str, recursive: bool, base_path, all) -> None:
        try:
            # ------------ soure
            src_name = self.clean_user_search(src)
            src_path = self.get_location_content_with_match(item_name=src_name, dir_location=dst_path, recursive=recursive)
            # ------------ destination 
            dst_path = Path(dst_path).expanduser()
            if not src_path:
                user_error(f'File matching \'{src}\' Not Found.')
                return
            table, items_dict = self.get_files_table(src_path)
            ids_to_copy = []
            if all:
                res = channel.make_request(prompt="[warning]Are you sure you want to copy all files? [yes -(y) /no -(n)][/]: ", table=table)
                if res.lower() not in ('yes', 'y'):
                    return
                ids_to_copy.extend(items_dict.keys())
            else:
                msg1 = f'You are about to copy the file above to {dst_path.name} confirm by passing the id of the file: '
                msg2 = f'More than one file matched \'{src}\' choose file(s) by id(s) to copy (q) to cancel, (a/all) for all matches: '
                msg = msg1
                if len(items_dict) > 1:
                    msg = msg2
                res = channel.make_request(prompt=msg, table=table)
                if not res:
                    return 
                elif res in ('a', 'all'):
                    ids_to_copy.extend(items_dict.keys())
                else:
                    selected_ids = normalize_ids(task_ids=res)
                    ids_to_copy.extend(selected_ids)

            def copy_file(i):
                try:
                    f = items_dict.get(i)
                    if not f:
                        user_error(f"Provided Invalid id {i}")
                        return
                    dst_path.mkdir(exist_ok=True, parents=True)
                    new_path = dst_path / f.name
                    if new_path.exists():
                        res = channel.make_request(f'{f.name} already in {dst_path.name} O-overide Q-cancel: ')
                        if res.lower() in ('q', 'cancel'):
                            return 
                        if res.lower() == 'o':
                            shutil.copy2(str(f), str(new_path))
                    else: 
                        if f.is_file():
                            shutil.copyfile(str(f), str(new_path))
                        elif f.is_dir():
                            shutil.copytree(str(f), str(new_path))
                    return True
                except (IOError, OSError) as exc:
                    raise
            results = ThreadPoolExecutor(max_workers=8).map(copy_file, ids_to_copy)
            success_count = sum(1 for result in results if result)
            user_success(f'Moved {success_count} file(s) to {dst_path.name}.')
            return
        except Exception as exc:
            user_error(str(exc))
            return
        
    def undo_move(self):
        try:
            if not LOG_FILE.exists():
                print('No undo History')
                return
            
            data = json.loads(LOG_FILE.read_text())
            if not data:
                print('There are no completed operation at this time')
                return
            
            entry = data.pop()

            dst = Path(entry.get('From'))
            src = Path(entry.get('To'))

            if not src.exists():
                print('Cannot undo move. file not found!')
                return
            
            dst.parents.mkdir(parents=True, exist_ok=True)
            destination = dst / src.name

            shutil.move(src, destination)
            user_success(f'Moved {src.name} from [cyan]{src.parent.name}[/] to [cyan]{destination.parent.name}[/]')
            return
        except Exception as exc:
            user_error(str(exc))

    def organize(self, source_dir: Path):
        initial_path = Path(source_dir).expanduser().absolute()

        try:
            files_paths = it.chain.from_iterable(initial_path.glob(p) for p in pattern)
            for file in files_paths:
                filename = file.stem.replace('.', '-').replace(' ', '-')
                ext = file.suffix.lower()

                target_dir = EXTENSION_MAP.get(ext, Downloads)
                for dir in target_dirs:
                    if dir in file.name.lower():
                        target_dir = target_dirs[dir]
                        break
                
                if file.parent == target_dir:
                    continue

                target_dir.mkdir(parents=True, exist_ok=True)
                destination = target_dir / f"{filename}{ext}"

                shutil.move(file, destination)
                user_success(f'Moved {file.name} from [cyan]{file.parent.name}[/] to [cyan]{destination.parent.name}[/]')

                self.log_move(file, destination)
        except Exception as e:
            user_error(f'An error Occurred: {type(e).__name__} {str}')(e)

    def parse_user_regex_search(self, filename: str, destination = None, base_path = None):
        source = re.sub(r'[^ a-zA-z0-9]+', ' ', filename)
        paths_list = []
        name = ".*".join(source.split(' '))
        for path in (destination, base_path):
            if path is None:
                continue
            new_path = Path(path).expanduser()
            new_path.mkdir(exist_ok=True, parents=True)
            paths_list.append(new_path)
        return name, paths_list

    def generate_response(self, msg1: str, msg2: str, file_dict: int, all: bool) -> str | list:
        """Queries user and gets returns user response"""
        result_ids = []
        if all:
            result_ids = [i for i in range(1, file_dict + 1)]

        else:
            msg_prompt = msg1
            if file_dict > 1:
                msg_prompt = msg2
            res = console.input(f'[warning]{msg_prompt}[/warning]')
            if res.lower() in ('q', 'cancel'):
                return res.lower()
            result_ids = normalize_ids(task_ids=res)
        return result_ids

    def search_files(self, pattern: str, base_path: Path, recursive: bool) -> list[PosixPath]:
        """search base path for pattern match"""
        compiled_pattern = re.compile(pattern + ".*", re.I)
        results = []
        if recursive:
            results = [f for f in base_path.rglob('**/*') if compiled_pattern.search(f.name)]
        else:
            results = [f for f in base_path.glob('*') if compiled_pattern.search(f.name)]
        return results
    
    def get_files_table(self, results: list) -> tuple[Table, dict]:
        file_dict = {}

        table = Table()
        table.show_lines = True
        table.padding = (0, 1, 0, 1 )
        table.add_column('id', justify='center')
        table.add_column('filename')
        table.add_column('filesize')

        for index, file in enumerate(results, start=1):
            mb = 1024 * 1024
            filesize = file.stat().st_size
            table.add_row(
                str(index), 
                file.name if file.is_file() else f"{file.name} Folder",
                f"{filesize // mb} mb" if filesize > mb else f"{filesize // 1024} Kb" # convert file to mb or kb depending on file size
            )
            file_dict[index] = file

        return table, file_dict