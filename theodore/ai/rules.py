import re
from pydantic import BaseModel, Field
from typing import List


RCLONE_REMOTE= re.compile(r"([\w_-]+):")
ENV_PATH= re.compile(r"([A-Z0-9_-]+)(?=[;,\s]|$)")
DIRECTORY= re.compile(r"(~/|/|./)\w+(?:/[\w-]+)*(?=[:;,\s]|$)")
FILEPATH= re.compile(r"\b[^\s]+(?:\.[\w]+)+")

def extract_entities(text):
    return {
    "filepath": FILEPATH.findall(text),
    "directory": DIRECTORY.findall(text),
    "env_path": ENV_PATH.findall(text),
    "rclone_remote": RCLONE_REMOTE.findall(text)
}

CONFIDENCE_THRESHOLD = 0.50

class IntentMetadata(BaseModel):
    filepath: List[str] = Field(default_factory=list)
    directory: List[str] = Field(default_factory=list)
    rclone_remote: List[str] = Field(default_factory=list)
    env_path: List[str] = Field(default_factory=list)


class RouteResult(BaseModel):
    intent: str
    confidence_level: float
    metadata: IntentMetadata


if __name__ == "__main__":
    backup = ["store backups inside /var/backups/local/serenity/locacallazi.txt", "./var/backups/local/serenity/locacalizzo tontirin", "scan everything under ~/projects azizam",]
    remotes =  ["upload files into s3:", "sync backups to gdrive: please", "this is my RCLONE_ENV_KEY fr", "./TRYANA-.SEEif something picks this."]
    filepath =  ["report.pdf", "upload config.json.dd", "compress logs.txt before uploading"]

    for regex in (RCLONE_REMOTE, ENV_PATH, DIRECTORY, FILEPATH):
        for txt in (t for tg in (backup, remotes, filepath) for t in tg):
            matches = regex.finditer(txt)
            for match in matches:
                print(f"Exp: {regex}\nMatch: {match.group(0)}\nText:  '{txt}'\n")
