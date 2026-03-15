from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.database import engine, Base
from app.api import invoices, review, reports
from app.core.logging import setup_logging, get_logger
from app.core.exceptions import InvoiceAutomationError

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("app_started")
    yield
    # Shutdown
    from app.agents.graph import close_graph
    await close_graph()
    await engine.dispose()
    logger.info("app_stopped")


app = FastAPI(title="Invoice Automation API", version="2.0.0", lifespan=lifespan)


@app.exception_handler(InvoiceAutomationError)
async def invoice_error_handler(request: Request, exc: InvoiceAutomationError):
    logger.error("unhandled_invoice_error", error=str(exc), path=request.url.path)
    return JSONResponse(status_code=400, content={"error": str(exc)})


app.include_router(invoices.router)
app.include_router(review.router)
app.include_router(reports.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
