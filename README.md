# Invoice Automation — Multi-Agent LangGraph System

I built this to solve a real problem: processing a pile of vendor invoices manually every month is tedious, error-prone, and doesn't scale. This system watches a folder, picks up PDFs automatically, runs them through a LangGraph multi-agent pipeline, and learns vendor patterns over time so repeat invoices don't even need a human to look at them.

The first invoice from any vendor goes to a human review queue. After you approve it once, the system remembers — future invoices from the same vendor auto-approve if confidence stays high. If confidence starts dropping (layout changed, new format), it flags it again automatically.

---

## How it actually works

```
PDF lands in data/incoming/
        ↓
   File Watcher (watchdog)
        ↓
   LangGraph Graph
        ↓
┌─────────────────────┐
│   DuplicateAgent    │ — checks filename against processed/ folder
└──────────┬──────────┘
┌──────────▼──────────┐
│  ExtractionAgent    │ — PyMuPDF first, Tesseract OCR fallback
└──────────┬──────────┘
┌──────────▼──────────┐
│  ValidationAgent    │ — required fields, confidence check, fallback rules
└──────────┬──────────┘
┌──────────▼──────────┐
│   TemplateAgent     │ — known vendor? auto-approve or flag layout change
└──────────┬──────────┘
┌──────────▼──────────┐
│     SaveAgent       │ — writes to Postgres, moves file
└──────────┬──────────┘
           ↓
   Human Review (Streamlit) — only if needed
           ↓
   Graph resumes via HITL, template learning kicks in
```

The graph pauses at the human review step using LangGraph's `interrupt()`. The invoice is already saved to the DB at that point, so it shows up in Streamlit immediately. When you click Approve, the graph resumes with your corrections via the thread ID.

---

## Stack

- **LangGraph** — multi-agent orchestration with HITL checkpointing (SQLite)
- **FastAPI** — async REST API
- **PostgreSQL** — invoice storage (SQLite in dev/tests)
- **Streamlit** — human review UI
- **PyMuPDF + Tesseract** — PDF text extraction with OCR fallback
- **GPT-4o-mini** — field extraction (~$0.0003/invoice)
- **watchdog** — file system monitoring
- **structlog** — structured JSON logging

---

## Getting started

### Prerequisites

- Docker + Docker Compose, **or** Python 3.11 + Tesseract + Poppler installed locally
- An OpenAI API key

### With Docker (easiest)

```bash
cp .env.example .env
# Add your OPENAI_API_KEY to .env

docker-compose up --build
```

That starts Postgres, the FastAPI backend, the file watcher, and Streamlit.

### Running locally

```bash
pip install -r requirements.txt

# Three terminals:
uvicorn app.main:app --reload          # terminal 1
streamlit run ui/streamlit_app.py      # terminal 2
python scripts/start_watcher.py        # terminal 3
```

### Environment variables

```
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/invoice_db
CONFIDENCE_THRESHOLD=0.85    # below this → human review
OCR_FALLBACK_CHAR_LIMIT=50   # fewer chars than this → try OCR
```

---

## Usage

1. Drop a PDF into `data/incoming/`
2. The watcher picks it up within a second and runs the pipeline
3. Open Streamlit at `http://localhost:8501`
4. If the invoice needs review, it appears in the **Pending Review** tab
5. Edit any fields, click Approve — the graph resumes and the vendor template activates
6. The next invoice from that vendor auto-approves (if confidence holds)

To export approved invoices to CSV:

```bash
python scripts/generate_csv.py
# or click "Generate & Download CSV" in the Streamlit UI
```

---

## Vendor template learning

This is the part I'm most happy with. The system isn't just a dumb extractor — it builds vendor profiles over time.

- First invoice from a vendor → LLM extracts, human reviews
- After first approval → vendor template activates, future invoices auto-approve
- System tracks confidence over the last 10 invoices per vendor
- If average confidence drops below 70% → template disabled, vendor flagged for review again (probably a layout change)
- After human approves again → template reactivates

---

## Scenarios at a glance

| What happens | Result |
|---|---|
| First invoice from a vendor | LLM extracts → human reviews → template activates |
| Repeat invoice, known vendor | Auto-approved, no human needed |
| Confidence drops (layout change) | Template disabled, back to human review |
| Scanned PDF with no text layer | OCR fallback via Tesseract |
| Same filename processed twice | Moved to `data/duplicates/`, skipped |
| Same invoice_number already in DB | IntegrityError caught, moved to duplicates |

---


