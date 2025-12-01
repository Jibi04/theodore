import itertools as it
from pathlib import Path 
import shutil
import subprocess
import datetime
import json
import re
from typing import Dict
from theodore.core.utils import user_success, user_error, JSON_DIR, TEMP_DIR, local_tz, normalize_ids, send_message
from rich.table import Table
from theodore.core.theme import console
from theodore.core.logger_setup import base_logger

HOME = Path.home()
Downloads = HOME / "Downloads"
Videos = HOME / "Videos"
Documents = HOME / "Documents"

LOG_FILE = JSON_DIR /  "file_manager_logs.json"


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
            results = self.search_files(pattern, base_path, recursive)
            if not results:
                user_error(f'File matching \'{pattern}\' Not Found.')
                return
            
            file_dict = {}
            file_dict.setdefault(1, results[0])
            table, file_dict = self.get_files_table(results)
            if not all:
                console.print(table)

            msg1 = 'You are about to delete the file above confirm by passing the id of the file: '
            msg2 = f'More than one file matched \'{pattern}\' choose file(s) by id(s) to delete (q) to cancel: '
            
            result_ids = self.generate_response(msg1=msg1, msg2=msg2, file_dict=len(file_dict), all=all)

            if not result_ids:
                user_error('Invalid Input')
                return
            
            if result_ids in ('q', 'cancel'):
                return

            for i in result_ids:
                try:
                    f = file_dict.get(i, None)
                    
                    # if f is file
                    if f.is_file():
                        f.unlink(missing_ok=True)
                    else:
                        # it's directory not file
                        shutil.rmtree(str(f))
                    user_success(f"{f.name} deleted")
                except (OSError, IOError) as exc:
                    continue
            return
        except Exception as exc:
            user_error(str(exc))
            return

    def move(self, src, dst, recursive, base_path, all) -> None:
        try:
            results = self.search_files(src, base_path, recursive)
            if not results:
                user_error(f'File Not Found in {str(base_path.absolute())}. Check file present destination or set absolute file path or None')
                return
            
            file_dict = {}
            file_dict.setdefault(1, results[0])
            table, file_dict = self.get_files_table(results)
            if not all:
                console.print(table)

            msg1 = f'You are about to move the file above to {dst.name} confirm by passing the id of the file: '
            msg2 = f'More than one file matched \'{src}\' choose file(s) by id(s) to Move (q) to cancel: '
            
            result_ids = self.generate_response(msg1=msg1, msg2=msg2, file_dict=len(file_dict), all=all)

            if not result_ids:
                user_error('Invalid Input')
                return
            
            if result_ids in ('q', 'cancel'):
                return

            for i in result_ids:
                try:
                    f = file_dict[i]
                    new_path = dst / f.name
                    if new_path.exists():
                        res = console.input(f'File already in {dst.name} O-overide Q-cancel: ')
                        if res.lower() in ('q', 'cancel'):
                            return 
                    shutil.move(str(f), str(new_path))
                    self.log_move(f, new_path)
                    print(f'Moved {f.name} from {f.parent.name} to {new_path.parent.name}')
                except (IOError, OSError) as exc:
                    continue
            return
            
        except Exception as exc:
            user_error(str(exc))
            return
    
    def copy(self, src, dst, base_path, recursive, all) -> dict:
        try:
            results = self.search_files(src, base_path, recursive)
            if not results:
                user_error(f'File matching \'{pattern}\' Not Found.')
                return
                
            file_dict = {}
            file_dict.setdefault(1, results[0])
            table, file_dict = self.get_files_table(results)
            if not all:
                console.print(table)

            msg1 = f'You are about to copy the file above to {dst.name} confirm by passing the id of the file: '
            msg2 = f'More than one file matched \'{src}\' choose file(s) by id(s) to copy (q) to cancel: '
            result_ids = self.generate_response(msg1=msg1, msg2=msg2, file_dict=len(file_dict), all=all)
            if not result_ids:
                user_error('Invalid Input')
                return
            
            if result_ids in ('q', 'cancel'):
                return
                
            for i in result_ids:
                try:
                    f = file_dict[i]
                    new_path = dst / f.name
                    if new_path.exists():
                        res = console.input(f'File already in {dst.name} O-overide Q-cancel: ')
                        if res.lower() in ('q', 'cancel'):
                            return 
                    if f.is_file():
                        shutil.copyfile(str(f), str(new_path))
                    else:
                        shutil.copytree(str(f), str(new_path))
                    user_success(f'Copied {f.name} from {f.parent.name} to {new_path.parent.name}')
                except (IOError, OSError) as exc:
                    continue
            return
        except Exception as exc:
            user_error(exc)
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
            self.log_move(src, destination)
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

    def parse_user_regex_search(self, source, destination = None, base_path = None):
        source = re.sub(r'[^ a-zA-z0-9]+', ' ', source)
        paths_list = []
        name = ".*".join(source.split(' '))
        for path in (destination, base_path):
            if path is None:
                continue
            new_path = Path(path).expanduser()
            new_path.mkdir(exist_ok=True, parents=True)
            paths_list.append(new_path)
        return name, paths_list

    def generate_response(self, msg1, msg2, file_dict, all):
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

    def search_files(self, pattern, base_path, recursive):
        compiled_pattern = re.compile(pattern + ".*", re.I)
        results = []
        if recursive:
            results = [f for f in base_path.rglob('*') if compiled_pattern.search(f.name)]
        else:
            results = [f for f in base_path.glob('*') if compiled_pattern.search(f.name)]
        return results
    
    def get_files_table(self, results):
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