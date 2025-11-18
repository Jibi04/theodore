from queue import PriorityQueue
import threading, json
from theodore.core.utils import JSON_DIR, error_logger

Queue = PriorityQueue()

worker_json = JSON_DIR / "worker.json"
def load_worker_json():
    try:
        worker_results = json.loads(worker_json.read_text())
        return worker_results
    except (OSError, json.JSONDecodeError):
        return {}

def worker():
    while True:
        _, (func, args) = Queue.get()

        try:
            results = load_worker_json()

            results[f"{func.__name__}:{args}"] = func(*args)

            worker_json.write_text(json.dumps(results, indent=4))
        except Exception as e:
            error_logger.error(f"Worker Failed: {type(e).__name__}: {str(e)}")
        finally:
            Queue.task_done()

# ----------- Create 5 threads --------------
for _ in range(5):
    threading.Thread(target=worker, daemon=True).start()
