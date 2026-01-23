import numpy as np
import concurrent.futures

from pathlib import Path
from typing import List, Tuple

from theodore.core.file_helpers import resolve_path

class LogSearch:
    def __init__(self, filepath, keywords: List[str], splitSize = 10):
        self.filepath = resolve_path(filepath)
        self.SplitSize = splitSize
        self._lastLocation: int = 0
        self._cumulative: np.ndarray | None = None
        self._keywords = keywords


    def getLogs(self) -> np.ndarray | None:
        if (path:=self.filepath.stat().st_size) == self._lastLocation:
            return self._cumulative
        
        splits = fileSplitter(filepath=self.filepath, splitSize=self.SplitSize, start=self._lastLocation)
        num_workers = len(splits)
        outerMatrix  = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            innerMatrices = executor.map(self.searchLogs, *zip(*splits))
            for matrix in innerMatrices:
                outerMatrix.append(matrix)

        if self._cumulative is None:
            self._cumulative = np.vstack(outerMatrix)
        else:
            self._cumulative = np.vstack((self._cumulative,outerMatrix))
        
        self._lastLocation = path
        return self._cumulative




    def searchLogs(self, startBytes, endBytes) -> List[np.ndarray]:
        innerMatrix = []
        with self.filepath.open('rb') as f:
            chunk = endBytes - startBytes
            
            # set marker
            f.seek(startBytes)
            dataTxt = f.read(chunk).decode(errors='ignore')
            for line in dataTxt.splitlines():
                innerMatrix.append(np.array([1 if word.lower() in line.lower() else 0 for word in self._keywords]))
        return innerMatrix



def fileSplitter(filepath: Path | str, splitSize: int, start: int=0) ->  List[Tuple[int, int]]:
    if not (path:=resolve_path(filepath)).exists():
        raise ValueError(f"Path {str(filepath)} could not be resolved.")
    
    filesize = path.stat().st_size
    approxChunk = filesize//splitSize
    currentPosition = start

    fileSplits = []

    with path.open('rb') as f:
        for i in range(splitSize):
            if i == splitSize - 1:
                fileSplits.append((currentPosition, filesize))
                break

            totalBytes = currentPosition + approxChunk

            # set marker
            f.seek(totalBytes)

            # read till the next line relative marker.
            f.readline()

            # get position and append
            safeEnd = f.tell()
            fileSplits.append((currentPosition, safeEnd))
            currentPosition = safeEnd
    return fileSplits


if __name__ == "__main__":
    filepath = Path("~/scripts/theodore/theodore/data/logs/errors.log").expanduser()
    KEYWORDS = ["timeout", "nonetype", "connection", "brokenpipe", "permission"]
    logs = LogSearch(keywords=KEYWORDS, filepath=filepath)
    matrix = logs.getLogs()
    # np.save("theodore/data/vectors/error_log_matrix.npy", matrix)

    print("<------------------ THEODORE HEALTH REPORT---------------->")
    column_sum = np.sum(matrix, axis=0)
    for col, freq in zip(KEYWORDS, column_sum):
        print(f"{col.upper()}: ", freq)