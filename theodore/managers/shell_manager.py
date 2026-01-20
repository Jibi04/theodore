import asyncio
import os
import time
import numpy

from dotenv import load_dotenv, find_dotenv
from pathlib import Path
from pydantic import BaseModel, ValidationError
from theodore.core.file_helpers import resolve_path
from theodore.core.utils import user_info
from theodore.core.logger_setup import vector_perf

class ValidateArgs(BaseModel):
    path: str | Path
    drive: str | None
    drive_env_key: str | None

class ShellManager:
    def __init__(self) -> None:
        file = find_dotenv()
        load_dotenv(file)

    async def custom_shell_cmds(self, cmd):
        if not isinstance(cmd, str):
            raise ValueError(f"Cannot understand non string commands. {cmd}")
        
        if "rm" in cmd.lower():
            return NotImplemented
        
        _cmd = cmd.split(" ")
        (returncode, stdout, stderr) = await subprocess(cmd=_cmd)
        message = stdout or stderr
        user_info(f"Return Code: {returncode}\n Message: {message}")
        return returncode

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
        
        cmd = ["rclone", "copy", str(p), cloud_path]
        (returncode, stdout, stderr) = await subprocess(cmd=cmd)
        message = stdout or stderr
        user_info(f"Return Code: {returncode}\n Message: {message}")
        return returncode

    async def stage(self, path = "."):
        if not (p:=resolve_path(path)).exists():
            raise ValueError(f"Path {path} could not be resolved.")
        
        cmd = ["git", "add", p]
        (returncode, stdout, stderr) = await subprocess(cmd=cmd)
        message = stdout or stderr
        user_info(f"Return Code: {returncode}\n Message: {message}")
        return returncode

    async def commit_git(self, message):
        cmd = ["git", "commit", "-m", message]
        (returncode, stdout, stderr) = await subprocess(cmd=cmd)
        message = stdout or stderr
        user_info(f"Return Code: {returncode}\n Message: {message}")
        return returncode
    
    async def alembic_upgrade(self):
        cmd = ["alembic", "upgrade", "head"]
        (returncode, stdout, stderr) = await subprocess(cmd=cmd)
        message = stdout or stderr
        user_info(f"Return Code: {returncode}\n Message: {message}")
        return returncode

    async def alembic_migrate(self, commit_message):
        cmd = ["alembic", "revision" "--autogenerate", "-m", commit_message]
        (returncode, stdout, stderr) = await subprocess(cmd=cmd)
        message = stdout or stderr
        user_info(f"Return Code: {returncode}\n Message: {message}")
        return returncode

    async def alembic_downgrade(self):
        cmd = ["alembic", "downgrade", "head"]
        (returncode, stdout, stderr) = await subprocess(cmd=cmd)
        message = stdout or stderr
        user_info(f"Return Code: {returncode}\n Message: {message}")
        return returncode


async def subprocess(cmd):
    start = time.perf_counter()
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    success = process.returncode
    end = time.perf_counter()
    vector_perf.internal(
        numpy.array(
            [
                1 if success else 0, 
                end - start, 
                len(stdout.decode()) 
                if success else 
                len(stderr.decode())
            ])
        )
    return success, stdout.decode(), stderr.decode()

