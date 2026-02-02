from contextlib import asynccontextmanager
from sqlalchemy import MetaData, Table
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from theodore.core.paths import get_db_path


DB = get_db_path()
engine = create_async_engine(DB, echo=False)
LOCAL_SESSION = async_sessionmaker(bind=engine)
meta = MetaData()

@asynccontextmanager
async def get_async_session():
    session: AsyncSession = LOCAL_SESSION()
    try:
        yield session
        await session.commit()

    except Exception:
        raise
    finally:
        await session.close()
        pass

async def drop_table(table: Table):
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: table.drop(sync_conn))
    print(f'{table.name} table dropped')

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(meta.create_all)
