# In theodore.core.worker_setup (or similar file)
import threading
import queue
import asyncio # Still needed to run async manager methods
# ... (other imports) ...

# 1. Define the Synchronous Queue
Queue = queue.Queue() 
NUM_WORKERS = 4 

# 2. The Synchronous Worker Function (Target for the Thread)
def worker():
    while True:
        # Get item from the synchronous queue (This blocks until an item is available)
        priority, (func, args) = Queue.get()

        try:
            # ⚠️ CRITICAL STEP: Run the ASYNC manager function in an event loop
            asyncio.run(func(*args)) 
            
            # ... (Any synchronous logging/DB updates after task completion) ...

        except Exception as e:
            # Handle logging/errors cleanly
            print(f"Sync Worker Failed: {type(e).__name__}: {str(e)}") 
        finally:
            # IMPORTANT: Mark the task as done
            Queue.task_done()

# 3. The Synchronous Starter Function
def start_workers(num_workers=NUM_WORKERS):
    """Starts workers as persistent threads."""
    for i in range(num_workers): 
        # Start a standard thread, targeting the synchronous worker function
        threading.Thread(target=worker, daemon=True, name=f'SyncWorker-{i+1}').start()
    
    # Wait a moment to ensure threads start
    # threading._sleep(0.1) # Using internal sleep or simple time.sleep(0.1)

# 4. The `put` Function (Synchronous)
def put_new_task(priority, funcname, args):
    """Puts a new item onto the synchronous queue."""
    # Ensure funcname is the async manager function (coroutine)
    Queue.put((priority, (funcname, args)))