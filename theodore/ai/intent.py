import json
import numpy as np
from pathlib import Path

from theodore.core.file_helpers import resolve_path
from theodore.core.utils import DATA_DIR
from sentence_transformers import SentenceTransformer
from theodore.core.exceptions import MissingParamArgument


class IntentRouter:
    def __init__(self, model: SentenceTransformer, train_data: Path | None = None, data_embeddings_path: Path | None = None, labels_embeddings_path: Path | None = None):
        if not (paths:=all((data_embeddings_path, labels_embeddings_path))) and train_data is None:
            raise MissingParamArgument(f"{self.__str__} Expects a 'data_embeddings_path' and 'labels_embeddings_path', or 'Train Data' but None was given.")
        
        self.model = model
        
        if paths:
            try:
                self.embeddings = np.load(str(data_embeddings_path))
                self.labels = json.loads(resolve_path(labels_embeddings_path).read_text())
            except OSError:
                raise
            except json.JSONDecodeError:
                raise
        elif train_data:
            try:
                data = json.loads(resolve_path(train_data).read_text())
            except json.JSONDecodeError:
                raise

            sentences = [txt for sentence_list in data.values() for txt in sentence_list]
            self.labels = [label for label, sentence_list in data.items() for _ in range(len(sentence_list))]

            embeddings = self.encode_text(sentences)
            self.embeddings = get_unit_vec(embeddings)

            embeddings_dir = DATA_DIR/"vector_embeddings"
            embeddings_dir.mkdir(exist_ok=True, parents=True)

            npy_path = embeddings_dir/"theodore_train_data_embeddings.npy"
            json_path = embeddings_dir/"theodore_train_data_labels.json"


            np.save(file=npy_path, arr=self.embeddings)
            json_path.write_text(json.dumps(self.labels))
    
    def match(self, text: str) -> tuple[str, float]:
        vector = self.encode_text(text)
        similarities =  get_similarity(self.embeddings, get_unit_vec(vector))

        best_idx = similarities.argmax()
        best_match = self.labels[best_idx]
        confidence = similarities[best_idx]

        return best_match, confidence
    
    def encode_text(self, text: str | list[str]) -> np.ndarray:
        return self.model.encode(text, convert_to_numpy=True, precision="float32")


def get_unit_vec(vector: np.ndarray):
    if vector.ndim > 1:
        return vector / np.linalg.norm(vector, keepdims=True, axis=1)
    return vector / np.linalg.norm(vector)


def get_similarity(V: np.ndarray, v: np.ndarray):
    return V @ v