import asyncio
import os
import time
import numpy

from dotenv import load_dotenv, find_dotenv
from pathlib import Path
from pydantic import BaseModel, ValidationError
from theodore.core.file_helpers import resolve_path

class ValidateArgs(BaseModel):
    path: str | Path
    drive: str | None
    drive_env_key: str | None

class ShellManager:
    def __init__(self) -> None:
        file = find_dotenv()
        load_dotenv(file)

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
        response = await subprocess(cmd=cmd)

    async def stage(self, path = "."):
        if not (p:=resolve_path(path)).exists():
            raise ValueError(f"Path {path} could not be resolved.")
        
        cmd = ["git", "add", p]
        response = await subprocess(cmd=cmd)

    async def commit_git(self, message):
        cmd = ["git", "commit", "-m", message]
        response = await subprocess(cmd=cmd)
    
    async def alembic_upgrade(self):
        cmd = ["alembic", "upgrade", "head"]
        response = await subprocess(cmd=cmd)

    async def alembic_migrate(self, commit_message):
        cmd = ["alembic", "revision" "--autogenerate", "-m", commit_message]
        response = await subprocess(cmd=cmd)

    async def alembic_downgrade(self):
        cmd = ["alembic", "downgrade", "head"]
        response = await subprocess(cmd=cmd)


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
    performance_vector = numpy.array([1 if success else 0, end - start, len(stdout.decode()) if success else len(stderr.decode())])

