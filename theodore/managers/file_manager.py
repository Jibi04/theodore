from concurrent.futures import CancelledError
from pathlib import Path
from rich.table import Table
from theodore.core.utils import normalize_ids, user_info
from theodore.core.transporter import CommunicationChannel
from theodore.core.file_helpers import *


class FileManager:
    def __init__(self):
        self.channel = CommunicationChannel()

    
    def organize_files(self, src: str | Path) -> None:
        if resolve_path(src).exists():
            organize(src_path=src)
            return
        user_error(f"Unknown File Path '{src}'")


    def move_file(self, src: Path | str, dst: Path | str , all: bool =False):
        """Move files from one location to another with shutil"""

        if resolve_path(src).exists():
            move_entry(src=src, dst=dst)
            return
        
        dest = resolve_path(dst)
        
        prompt = f'Your search matched the above file(s). to move to {dest.name} confirm by passing the id(s) of the file(s) (q) to quit: '
        if all: prompt = "[warning]Are you sure you want to move all files? [yes -(y) /no -(n)]: "

        response = self.process_non_conventional(func=move_entry, dst=dest, src=str(src), prompt=prompt)
        if response:
            user_info(f"{response} tasks moved.")

        return 


    def move_dst_unknown(self, src):
        if resolve_path(src).exists():
            dst, _src = move_unknown_destination(src=src)
            user_info(f"moved '{_src.name}' to '{dst.name}'")


    def copy_file(self, src: Path | str, dst: Path | str , all: bool =False):
        """Move files from one location to another with shutil"""

        if resolve_path(src).exists():
            copy_entry(src=src, dst=dst)
            return
        
        dest = resolve_path(dst)

        prompt = f'Your search matched the above file(s). to copy to {dest.name} confirm by passing the id(s) of the file(s) (q) to quit: '
        if all: prompt = "[warning]Are you sure you want to copy all files? [yes -(y) /no -(n)]: "

        response = self.process_non_conventional(func=copy_entry, dst=dest, src=str(src), prompt=prompt)
        if response:
            user_info(f"{response} tasks copied.")
        return 
    
    
    def undo_move(self):
        return undo()


    def delete_file(self, *, src: Path | str, all: bool = False) -> None:
        if resolve_path(src).exists():
            delete_entry(src)
            return
        
        prompt = f'Your search matched the above file(s). to delete any file(s) confirm by passing the id(s) of the file(s) (q) to quit: '
        if all: prompt = "[warning]Are you sure you want to delete all file(s) match? [yes -(y) /no -(n)]: "
        response = self.process_non_conventional(src=str(src), func=delete_entry, prompt=prompt, dst=Path.home())

        if response:
            user_info(f"{response} tasks copied.")
        return


    def list_all_files(self, *, target_dir: str | Path) -> list[Any]:
        # yet to determine it's functionality
        if resolve_path(target_dir).exists():
            return list(iter_dir_content(target_dir))
        
        dirname = clean_user_search(target_dir)
        matches = search_with_match(entry_name=dirname, recursive=True)

        directories = [f for f in matches if f.is_dir()]
        files = list()

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            for dir in directories:
                try:
                    task = executor.submit(iter_dir_content, path=dir, recursive=True)
                    files.append(task.result(timeout=60))
                except CancelledError:
                    files.append(f"{dir.name} took too long got cancelled.")
                    continue

        return files
    

    # def list_all_files(self, *, target_dir: str | Path) -> list[Any]:
    # _target = resolve_path(target_dir)
    # if _target.exists():
    #     return list(iter_dir_content(_target))
    
    # dirname = clean_user_search(target_dir)
    # matches = search_with_match(entry_name=dirname, recursive=True)
    # directories = [f for f in matches if f.is_dir()]
    
    # files = []
    # with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
    #     # Submit all tasks at once
    #     future_to_dir = {executor.submit(iter_dir_content, path=d, recursive=True): d for d in directories}
        
    #     for future in concurrent.futures.as_completed(future_to_dir):
    #         d = future_to_dir[future]
    #         try:
    #             files.extend(list(future.result())) # use extend for a flat list
    #         except Exception as e:
    #             files.append(f"Error reading {d.name}: {e}")
    # return files



    def whereis(self, *, target_name: str | Path) -> list[Any]:
        name = clean_user_search(target_name)
        matches = search_with_match(entry_name=name, recursive=True)
        # still in the works


    def process_non_conventional(self, *, func: Any, dst: str | Path, src: str, prompt: str):

        filename = clean_user_search(src)
        print(filename)
        matches = search_with_match(entry_name=filename, recursive=True)

        if not matches:
            user_info(f"Theodore is unable to find file with name '{src}'")
            return
        
        table, match_dict = self.get_files_table(results=matches)
        response = self.channel.make_request(
            prompt=prompt,
            table=table
        )

        match response.lower():
            case "q" | "n" | "no":
                return
            case "all" | "a":
                report = bulk_run(func, dst=dst, records=match_dict)
            case _:
                ids = normalize_ids(task_ids=response)
                report = bulk_run(func, records=match_dict, indices=ids, dst=dst)

        return report


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
                file.name if file.is_file() else f"[bold cyan]{file.name}[/]",
                f"{filesize // mb} mb" if filesize > mb else f"{filesize // 1024} Kb" # convert file to mb or kb depending on file size
            )
            file_dict[index] = file

        return table, file_dict
    
