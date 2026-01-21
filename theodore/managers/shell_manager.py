import asyncio
import os
import re
import time
import numpy


from enum import IntEnum
from dotenv import load_dotenv, find_dotenv
from pathlib import Path
from pydantic import BaseModel, ValidationError
from rich.layout import Layout
from rich.live import Live
from rich.progress import Progress, BarColumn, TextColumn, ProgressColumn
from theodore.core.file_helpers import resolve_path
from theodore.core.utils import user_info
from theodore.core.logger_setup import vector_perf

class ValidateArgs(BaseModel):
    path: str | Path
    drive: str | None
    drive_env_key: str | None


class TaskID(IntEnum):
    Git = 1
    Alembic = 2
    Extraction = 3
    Compression = 4
    Backup = 5


class ShellManager:
    def __init__(self) -> None:
        file = find_dotenv()
        load_dotenv(file)

    def _extract_file_count(self, cmd, stdout, stderr):
        combined_output = stdout + "\n" + stderr
        workdone = 0

        match cmd:
            case "git":
                count = re.search(r"(\d+)\s+files? changed", combined_output)
                workdone = int(count.group(1)) if count else 0
                task_id = TaskID.Git
            case "rclone":
                match = re.search(r"Transfered:\s(\d+)\s+/", combined_output)
                workdone = int(match.group(1)) if match else 0
                task_id = TaskID.Backup
            case "alembic":
                workdone = int(stdout.count("Running upgrade"))
                task_id = TaskID.Alembic
            case _:
                workdone = 0
                task_id = 0

        error_weight = len(stderr.splitlines()) if stderr.strip() else 0
        return task_id, workdone, error_weight

        

    async def custom_shell_cmd(self, cmd):
        if not isinstance(cmd, str):
            raise ValueError(f"Cannot understand non string commands. {cmd}")
        
        if "rm" in cmd.lower():
            return NotImplemented
        
        _cmd = cmd.split(" ")
        return await self.runcommand(cmd=_cmd, cmd_for="custom")

    async def backup_files_rclone(self, path: str | Path, drive: str | None = None, drive_env_key: str | None = None):
        try:
            data = ValidateArgs(path=path, drive=drive, drive_env_key=drive_env_key)
        except ValidationError as e:
            raise e

        cloud_path = data.drive
        if data.drive_env_key:
            cloud_path = os.getenv(data.drive_env_key)
        if cloud_path is None:
            raise ValueError("No destination path nor environment key provided.")
        
        if not (p:=resolve_path(path)).exists():
            raise ValueError(f"Path {path} could not be resolved.")
        
        cmd = ["rclone", "copy", str(p), cloud_path, "--progress", "--stats", "1s"]
        return await subprocess_with_progress(cmd=cmd)

    async def stage(self, path = "."):
        if not (p:=resolve_path(path)).exists():
            raise ValueError(f"Path {path} could not be resolved.")
        
        cmd = ["git", "add", p]
        return await self.runcommand(cmd=cmd, cmd_for="git")

    async def commit_git(self, message: str):
        cmd = ["git", "commit", "-m", message]
        return await self.runcommand(cmd=cmd, cmd_for="git")
    
    async def alembic_upgrade(self):
        cmd = ["alembic", "upgrade", "head"]
        return await self.runcommand(cmd=cmd, cmd_for="alembic")

    async def alembic_migrate(self, commit_message: str):
        cmd = ["alembic", "revision" "--autogenerate", "-m", commit_message]
        return await self.runcommand(cmd=cmd, cmd_for="alembic")

    async def alembic_downgrade(self):
        cmd = ["alembic", "downgrade", "head"]
        return await self.runcommand(cmd=cmd, cmd_for="alembic")
    
    async def runcommand(self, cmd, cmd_for):
        start = time.perf_counter()
        (returncode, stdout, stderr) = await subprocess(cmd=cmd)
        duration = round(time.perf_counter() - start, 3)
        (tid, workdone, errorweight) = self._extract_file_count(cmd=cmd_for, stdout=stdout, stderr=stderr)
        vector_perf.internal(numpy.array(
            [   
                tid,
                1 if returncode == 0 else 0, 
                duration, 
                workdone, 
                errorweight
            ]))
        return 1 if returncode == 0 else 0


async def subprocess(cmd):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=Path(__file__).parent.parent.parent
    )

    stdout, stderr = await process.communicate()
    return process.returncode, stdout.decode(), stderr.decode()

async def subprocess_with_progress(cmd, description="Processing..."):
    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%")
    )

    backup_task = progress.add_task(description=description, total=100)
    layout = Layout()
    layout.update(progress)

    with Live(layout, refresh_per_second=5):
        start = time.perf_counter()
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        errors_decoded = []
        while True:
            line = await process.stderr.readline() + await process.stdout.readline()
            if not line:
                break

            decoded_line = line.decode().strip()
            errors_decoded.append(decoded_line)

            match = re.search(r"Transferred:\s+(\d+)%,\s", decoded_line)
            print(match)
            if match:
                progress.update(backup_task, completed=int(match.group(1)))

        await process.wait()

        stop = time.perf_counter()
        returncode = process.returncode

        stderr = " ".join(errors_decoded)

        search_string = stderr + "\n" + process.stdout.decode()

        workdone = 0
        match = re.search(r'Transferred:\s+(\d+)\s+/', search_string)
        if match:
            workdone = match.group(1)

        vector_perf.internal(numpy.array(
            [TaskID.Backup, 
             1 if returncode == 0 else 0, 
             stop - start,
             workdone,
             len(stderr.splitlines()) if stderr else 0
            ]
        ))
        return returncode