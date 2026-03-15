import asyncio
from app.database import AsyncSessionLocal
from app.services.csv_exporter import generate_csv
from app.core.logging import setup_logging


async def main():
    setup_logging()
    async with AsyncSessionLocal() as db:
        path = await generate_csv(db, limit=1000)
        print(f"CSV exported to: {path}")


if __name__ == "__main__":
    asyncio.run(main())
