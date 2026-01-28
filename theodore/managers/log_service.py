import numpy as np

class LogService:
    def search(self, txt):...

    def vectorize_txt(self, txt):...

    def detect_anomaly(self):...



def arr_to_bytes(arr: np.ndarray):
    return arr.tobytes()

def arr_from_bytes(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob,dtype=np.float32)


