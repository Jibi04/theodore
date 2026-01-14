import subprocess
import os
from dotenv import load_dotenv, find_dotenv
from pathlib import Path
from pydantic import BaseModel
from typing import Mapping, List


class User(BaseModel):
    username: str
    token: str

class Command(BaseModel):
    cmd: List[str]
    work_dir: str

class FullProcess(BaseModel):
    branch: str
    message: str
    token: str


class GitAutomation:
    CMD_REGISTRY = {
        "SOFT": ["git", "reset", "--soft", "HEAD~1"],
        "HARD": ["git", "reset", "--hard", "HEAD~1"],
        "UNSTAGE": ["git", "reset", "HEAD~1"],
        "UNTRACK_FILE": ["git", "rm", "--cached"],
        "UNTRACK_FOLDER": ["git", "rm", "-r", "--cached"],
        "REVERT": ["git", "revert"],
        "PUSH": ["git", "push"],
    }

    def __init__(self, username, work_directory = "~/scripts/theodore/"):
        env = find_dotenv()
        load_dotenv(env)
        self.username = username
        self.__token = os.environ.get(f"git-{self.username}")
        self.__work_directory = work_directory


    def send_command(self, cmd: List[str]) -> dict:
        data = Command(cmd=cmd, work_dir=self.__work_directory)
        try:
            result = subprocess.run(
                    cmd=data.cmd,
                    cwd=data.work_dir,
                    text=True,
                    capture_output=True
                )
            return self.__send_message(result.returncode, result.stdout.strip("\n"))
        except subprocess.CalledProcessError as e:
            return self.__send_message(e.returncode, e.stderr.strip("\n"))
        

    def full_process_with_token(self, branch: str, message: str= "") -> dict:
        data = FullProcess(branch=branch, message=message, token=self.__token)
        try:
            cmd = f"git add . && git commit -m {data.message} && git push {data.token} {data.branch}"
            result = subprocess.run(
                            cmd=cmd,
                            cwd=self.__work_directory,
                            shell=True,
                            capture_output=True,
                            text=True
                            )
            return self.__send_message(returncode=result.returncode, message=result.stdout.strip("\n"))
        except subprocess.CalledProcessError as e:
            return self.__send_message(e.returncode, e.stderr.strip("\n"))


    def uncommit(self, cmd_type: str = "SOFT") -> dict:
        cmd = GitAutomation.CMD_REGISTRY.get(cmd_type, None)
        if cmd is None:
            return {}
        return self.send_command(cmd)


    def revert(self, commit_hash = "HEAD") -> dict:
        cmd = GitAutomation.CMD_REGISTRY.get("REVERT")
        if self.__token is None:
            return {}
        cmd.extend([commit_hash, "--no-commit"])
        return self.send_command(cmd=cmd)
    

    def git_logs(self) -> dict:
        cmd = ["git", "log", "--oneline"]
        return self.send_command(cmd=cmd)
    

    def git_status(self) -> dict:
        cmd = ["git", "status"]
        return self.send_command(cmd=cmd)

    
    def remove_tracking(self, fullpath: str, filetype: str = "FILE") -> dict:
        if not self.resolve_path(fullpath):
            return {}
        cmd = GitAutomation.CMD_REGISTRY.get(filetype, None)
        if cmd is None:
            return {}
        
        cmd.append(fullpath)
        return self.send_command(cmd)
    
    
    def git_push(self) -> dict:
        cmd = GitAutomation.CMD_REGISTRY.get("PUSH")
        cmd.append(self.__token)

        return self.send_command(cmd=cmd)
        

    def resolve_path(filepath) -> bool:
        return Path(filepath).exists()


    # Instanciating a class just to set-token is waste of Memory and memory referencing
    @staticmethod
    def set_token(token, username: str= "Jibi04") -> None:
        data = User(username=username, token=token)
        os.environ.setdefault(f"git-{data.username}", data.token)
        return
    

    def __send_message(self, returncode: float, message: str) -> dict:
        return {"returncode": returncode, "message": message}


