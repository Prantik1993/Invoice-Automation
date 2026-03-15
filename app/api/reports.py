from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.csv_exporter import generate_csv

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/export-csv")
async def export_csv(limit: int = 1000, db: AsyncSession = Depends(get_db)):
    path = await generate_csv(db, limit=limit)
    return FileResponse(path, media_type="text/csv", filename=path.split("/")[-1])
