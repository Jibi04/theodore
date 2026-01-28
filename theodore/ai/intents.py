import json
import numpy as np

from pathlib import Path
from typing import Dict, List
from sentence_transformers import SentenceTransformer
from theodore.core.utils import DATA_DIR
from theodore.ai.train_data import DEFAULT_TRAIN_DATA


class IntentIndex:
    def __init__(
            self,
            *, 
            model: SentenceTransformer, 
            embeddings_path: Path | str | None = None, 
            labels_path: Path | str | None = None, 
            train_data: Dict[str, List[str]] = DEFAULT_TRAIN_DATA
        ):
        self.model = model

        if not (paths:=all((embeddings_path, labels_path))) and train_data is None:
            raise 

        if paths:
            self.embeddings_unit_vector = np.load(str(embeddings_path))
            self.labels = json.loads(str(labels_path))
        else:
            labels = []
            texts = []

            for label, sentences in train_data.items():
                for txt in sentences:
                    texts.append(txt)
                    labels.append(label)

            self.embeddings = self.model.encode(texts)
            self.embeddings_unit_vector = self.embeddings/np.linalg.norm(self.embeddings, axis=1, keepdims=True)

            np.save("embeddings_unit_vector.npy", arr=self.embeddings_unit_vector)
            Path("embeddings_labels.json").write_text(json.dumps(labels))


    def match(self, vector: np.ndarray) -> tuple[str, float]:
        matches = self._calc_dot(vector)
        best_idx = matches.argmax()
        best_match = matches[best_idx]
        return self.labels[best_idx], best_match
        
    def _calc_dot(self, vector) -> np.ndarray:
        unit_vector = vector/np.linalg.norm(vector)
        return self.embeddings_unit_vector @ unit_vector


embeddings_dir = DATA_DIR/"vector_embeddings"
embeddings_dir.mkdir(parents=True, exist_ok=True)

embed_label_path = embeddings_dir/"cmd_labels.json"
embed_npy_path = embeddings_dir/"cmd_embeddings.npy"


if __name__ == "__main__":
    model = SentenceTransformer("all-MiniLM-L6-v2")
    all_sentences = [txt for label_grp in DEFAULT_TRAIN_DATA.values() for txt in label_grp]
    labels = [label for label, val in DEFAULT_TRAIN_DATA.items() for _ in range(len(val))]

    cmd_json = json.dumps(labels)
    embeddings_vectors = model.encode(all_sentences)

    embed_label_path.write_text(cmd_json)
    np.save(file=embed_npy_path, arr=embeddings_vectors)

    print("----------------- Embeddings Done ----------------")
    print("cmd map: \n", cmd_json)
    print()
    print("Embeddings: \n", embeddings_vectors)
