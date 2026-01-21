import concurrent.futures
import numpy as np


from numpy import ndarray
from pathlib import Path
from typing import List
from theodore.core.file_helpers import resolve_path


class LogSearch:
    def __init__(self, filepath: str | Path, keywords: List[str], split_size: int, num_workers: int = 10):
        self.filepath = resolve_path(filepath)
        self.keywords = keywords
        self.split_size = split_size
        self.num_workers = num_workers

    def __search_logs(self, start: int, end: int) -> List[ndarray]:
        inner_matrix = []

        with self.filepath.open('rb') as f:
            chunk = end - start
            f.seek(start)
            data_txt = f.read(chunk).decode(errors="ignore")
            for line in data_txt.splitlines():
                inner_matrix.append(np.array([1 if word in line.lower() else 0 for word in self.keywords]))

        return inner_matrix
    
    def get_logs(self) -> ndarray:
        matrix = []
        bytes_split = get_log_split(filepath=self.filepath, split_size=self.split_size)
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = executor.map(self.__search_logs, *zip(*bytes_split))
            for inner_matrix in futures:
                matrix.extend(inner_matrix)

        return np.vstack(matrix)


def get_log_split(filepath: str | Path, split_size: int) -> List[tuple[int]]:
    path = resolve_path(filepath)
    filesize = path.stat().st_size

    chunksize = filesize//split_size
    start = 0

    splits = []
    with path.open('rb') as f:
        for i in range(split_size):
            if i == split_size -1:
                splits.append((start, filesize))
                break

            f.seek(start + chunksize)
            f.readline()
            safe_end = f.tell()

            splits.append((start, safe_end))
            start = safe_end

    return splits



if __name__ == "__main__":
    _file = Path("~/scripts/theodore/theodore/data/logs/theodore.log").expanduser()
    KEYWORDS = ["timeout", "nonetype", "connection", "brokenpipe", "permission"]
    logs = LogSearch(keywords=KEYWORDS, filepath=_file, split_size=15)
    matrix = logs.get_logs()
    # np.save("theodore/data/vectors/error_log_matrix.npy", matrix)

    print("<------------------ THEODORE HEALTH REPORT---------------->")
    column_sum = np.sum(matrix, axis=0)
    for col, freq in zip(KEYWORDS, column_sum):
        print(f"{col.upper()}: ", freq)