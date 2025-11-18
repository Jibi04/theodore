import itertools as it
from pathlib import Path 
import shutil
import subprocess
import datetime
import json
import re
from typing import Dict
from theodore.core.utils import send_message, user_success, user_error, JSON_DIR

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

pattern = ['*.mkv', '*.mp4', '*.deb', '*.sh', '*.pdf', '*.docx', '*.tar', '*.zip', '*.csv', '*.xlsx'] 

class File_manager:

    def delete(self, pattern, base_path, recursive=False):
        pattern = re.compile(pattern, re.I)
        results = []

        if recursive:
            results = [f for f in base_path.rglob('*') if pattern.search(f.name)]
        else:
            results = [f for f in base_path.glob('*') if pattern.search(f.name)]

        if not results:
            return user_error("Not found")
        
        for f in results:
            path = Path(f)
            if path.is_file():
                path.unlink(missing_ok=True)
                user_success(f"{path.name} deleted")
                return 
            shutil.rmtree(str(path))
            user_success(f"{path.name} deleted")
            return


    def move(self, src, dst, recursive, base_path) -> None:
        if dst.exists():
            print('File already exists')
            return
        
        
        
        pattern = re.compile(pattern, re.IGNORECASE)
        results = []

        if recursive:
            results = [f for f in base_path.rglob('*') if pattern.search(f.name)]
        else:
            results = [f for f in base_path.glob('*') if pattern.search(f.name)]

        if not results:
            return user_error("Not found")
        
        for f in results:
            path = Path(f)
            if path.is_file():
                path.unlink(missing_ok=True)
                user_success(f"{path.name} deleted")
                return 
            shutil.rmtree(str(path))
            user_success(f"{path.name} deleted")
            return
        
        shutil.move(src, dst)
        print(f'Moved {src.name} from {src.parent.name} to {dst.parent.name}')
        return
    
    def copy(self, src, dst) -> dict:
        if dst.exists():
            print('File already exists')
            return
        
        shutil.copyfile(src, dst)
        print(f'Moved {src.name} from {src.parent.name} to {dst.parent.name}')
        return

    def log_move(self, src: Path, dst: Path):
        entry = {
            "From": str(src),
            "To": str(dst),
            "Timestamp": datetime.datetime.now().isoformat(sep=" ")
        }

        old = []

        if LOG_FILE.exists():
            try:    
                old = json.loads(LOG_FILE.read_text())
            except json.JSONDecodeError:
                pass
        
        old.append(entry)
        LOG_FILE.write_text(json.dumps(old, indent=2))


    def undo_move(self):
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
        
        dst.mkdir(parents=True, exist_ok=True)
        destination = dst / src.name

        shutil.move(src, destination)
        self.log_move(src, destination)
        user_success(f'Moved {src.name} from [cyan]{src.parent.name}[/] to [cyan]{destination.parent.name}[/]')



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
