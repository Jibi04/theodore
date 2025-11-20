import asyncio
from sqlalchemy import insert
from asyncio import PriorityQueue as AsyncPriorityQueue
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

from theodore.models.base import engine
from theodore.core.utils import user_error, local_tz
from theodore.models.file import Queues

Queue = AsyncPriorityQueue()

async def worker():
    while True:
        _, (func, args) = await Queue.get()

        try:
            async with engine.begin() as conn:

                response = func(*args)
                query = insert(Queues)
                if response:
                    message= response.get('message')
                    data = response.get('data', {})
                    date = response.get('date', datetime.now(local_tz))
                    query = query.values(func_name=func.__name__, args=args, message=message, data=data, date=date)
                else: query = query.values(func_name=func.__name__, args=args, date=datetime.now(local_tz))
                
                await conn.execute(query)
        except SQLAlchemyError as exc:
            user_error(str(exc))
        except Exception as e:
            user_error(f"Worker Failed: {type(e).__name__}: {str(e)}")
        finally:
            Queue.task_done()

async def start_workers(num_workers):
    for _ in range(num_workers):
        asyncio.create_task(worker())
    
    await Queue.join()

async def put_new_task(priority, funcname, args):
    await Queue.put((priority, (funcname, args)))