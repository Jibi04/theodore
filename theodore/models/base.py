import asyncio
from contextlib import asynccontextmanager
from sqlalchemy import MetaData, inspect
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from pathlib import Path
from theodore.core.utils import base_logger, DATA_DIR

DB_DIR = DATA_DIR
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "theodore.sqlite"


DB = f"sqlite+aiosqlite:///{DB_PATH}"
# engine = create_async_engine(DB, echo=True) 

engine = create_async_engine(DB, echo=False)
LOCAL_SESSION = async_sessionmaker(bind=engine)
meta = MetaData()

@asynccontextmanager
async def get_async_session():
    session: AsyncSession = LOCAL_SESSION()
    try:
        async with session.begin() as session:
            yield session

    except Exception:
        raise
    finally:
        await session.close()

async def create_tables():
    base_logger.internal('Connecting to the database engine')
    async with engine.begin() as conn:
        base_logger.internal('Creating all db tables')
        await conn.run_sync(meta.create_all)



# ------------------------
# pseudo setup
# ------------------------

# async def count_tables():
#     async with engine.connect() as conn:
#         def get_tables(sync_conn):
#             inspector = inspect(sync_conn)
#             return inspector.get_table_names()
        
#         tables = await conn.run_sync(get_tables)
#         return len(tables), tables

    
# async def main():
#     count, tables = await count_tables()
#     print(f"{count} tables found:", tables)


# asyncio.run(main())
