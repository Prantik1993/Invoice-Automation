# Invoice Automation — Multi-Agent LangGraph System

Automated invoice processing pipeline using LangGraph agents, FastAPI, PostgreSQL, and Streamlit.

## Architecture

```
PDF Drop → File Watcher → LangGraph Graph
                              │
                    ┌─────────▼──────────┐
                    │   DuplicateAgent   │ → duplicate/ folder
                    └─────────┬──────────┘
                    ┌─────────▼──────────┐
                    │  ExtractionAgent   │ → text → OCR fallback → LLM
                    └─────────┬──────────┘
                    ┌─────────▼──────────┐
                    │  ValidationAgent   │ → confidence + field check
                    └─────────┬──────────┘
                    ┌─────────▼──────────┐
                    │  TemplateAgent     │ → vendor auto-approve / layout change
                    └─────────┬──────────┘
                    ┌─────────▼──────────┐
                    │    SaveAgent       │ → PostgreSQL + file move
                    └────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   Streamlit UI     │ → human review & approve
                    └────────────────────┘
```

## Quick Start

### 1. Setup environment
```bash
cp .env.example .env
# Add your OPENAI_API_KEY to .env
```

### 2. Run with Docker (recommended)
```bash
docker-compose up --build
```

### 3. Run locally
```bash
pip install -r requirements.txt

# Terminal 1 — API
uvicorn app.main:app --reload

# Terminal 2 — Streamlit UI
streamlit run ui/streamlit_app.py

# Terminal 3 — File Watcher
python scripts/start_watcher.py
```

## Usage

1. Drop PDF invoices into `data/incoming/`
2. Watcher detects them and runs the LangGraph pipeline automatically
3. Open Streamlit UI at `http://localhost:8501`
4. Review, edit, and approve pending invoices
5. After first approval for a vendor → future invoices auto-approve
6. Export CSV: click "Generate & Download CSV" in Streamlit or run:
   ```bash
   python scripts/generate_csv.py
   ```

## Key Behaviours

| Scenario | Result |
|---|---|
| First invoice from vendor | → LLM extracts → human review |
| After first approval | → vendor template activated |
| Same vendor, high confidence | → auto-approved |
| Confidence drops < 70% (last 10) | → layout change detected, template disabled |
| Scanned PDF (no text) | → OCR fallback via Tesseract |
| Duplicate invoice | → moved to `data/duplicates/` |

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/invoices/pending` | Pending review queue |
| GET | `/invoices/` | All invoices |
| PUT | `/review/{id}/approve` | Approve with corrections |
| PUT | `/review/{id}/reject` | Reject invoice |
| POST | `/reports/export-csv` | Download CSV |
| GET | `/health` | Health check |

## Running Tests
```bash
pytest tests/ -v
```

## Cost Estimate
- ~$0.0003 per invoice (GPT-4o-mini)
- 1000 invoices/day ≈ $9/month in LLM costs
