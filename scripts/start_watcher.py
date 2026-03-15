"""File watcher — monitors data/incoming/ and triggers the LangGraph pipeline.

Uses a single persistent event loop shared across all PDF processing to avoid
asyncio conflicts with aiosqlite. Each PDF gets a unique thread_id for
checkpointing and HITL resume.
"""
import asyncio
import time
import uuid
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.agents.graph import get_graph, make_initial_state
from app.config import settings
from app.core.logging import setup_logging, get_logger

logger = get_logger("watcher")

_loop: asyncio.AbstractEventLoop = None


def get_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


async def init_db():
    """Create all DB tables before processing starts. Safe to call multiple times."""
    from app.database import engine, Base
    from app.models import invoice, vendor_template  # noqa — registers models with SQLAlchemy
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("db_tables_ready")


class InvoicePDFHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".pdf"):
            return

        pdf_path = event.src_path
        pdf_filename = Path(pdf_path).name
        logger.info("pdf_detected", filename=pdf_filename)

        time.sleep(1)  # Give the OS time to finish writing the file

        loop = get_loop()
        future = asyncio.run_coroutine_threadsafe(
            self._process(pdf_path, pdf_filename), loop
        )
        try:
            future.result(timeout=settings.pdf_processing_timeout)
        except Exception as e:
            logger.error("pdf_processing_error", filename=pdf_filename, error=str(e))

    async def _process(self, pdf_path: str, pdf_filename: str):
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = make_initial_state(pdf_path, pdf_filename, thread_id=thread_id)

        try:
            graph = await get_graph()
            result = await graph.ainvoke(initial_state, config=config)

            status = result.get("status", "unknown")
            logger.info(
                "pdf_processed",
                filename=pdf_filename,
                status=status,
                invoice_id=result.get("invoice_id"),
                thread_id=thread_id,
            )

            if status == "processing":
                logger.info("graph_paused_awaiting_hitl", thread_id=thread_id, filename=pdf_filename)

            for entry in result.get("agent_log", []):
                logger.info("agent_log", entry=entry)

        except Exception as e:
            logger.error("graph_failed", filename=pdf_filename, error=str(e), thread_id=thread_id)


def start_watching():
    setup_logging()

    incoming = settings.incoming_folder
    Path(incoming).mkdir(parents=True, exist_ok=True)

    loop = get_loop()
    loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
    loop_thread.start()

    future = asyncio.run_coroutine_threadsafe(init_db(), loop)
    future.result(timeout=settings.db_init_timeout)

    observer = Observer()
    observer.schedule(InvoicePDFHandler(), path=incoming, recursive=False)
    observer.start()
    logger.info("watcher_started", folder=incoming)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        loop.call_soon_threadsafe(loop.stop)

    observer.join()


if __name__ == "__main__":
    start_watching()