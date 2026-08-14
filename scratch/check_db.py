import asyncio
from backend.app.database import SessionFactory
from sqlalchemy import text

async def main():
    async with SessionFactory() as session:
        r1 = await session.execute(text("SELECT status, count(*) FROM signal_events GROUP BY status"))
        print("EVENTS:", dict(r1.all()))
        r2 = await session.execute(text("SELECT status, count(*) FROM signal_jobs GROUP BY status"))
        print("JOBS:", dict(r2.all()))

if __name__ == "__main__":
    asyncio.run(main())
