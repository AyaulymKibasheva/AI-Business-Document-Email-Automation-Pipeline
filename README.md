# AI Business Document & Email Automation Pipeline

A structured foundation for an AI-powered business document processing and
workflow automation system.

## Project structure

```text
app/          Application modules
data/         Local input and generated data
logs/         Application logs
tests/        Automated tests
```

## Current features

- Organized application skeleton (stage 1)
- Manual PDF, DOCX, and TXT document intake (stage 2)
- File existence and supported-type validation
- Plain-text extraction from PDF, DOCX, and TXT files (stage 3)
- Extraction error logging to `logs/app.log`
- AI classification into invoice, purchase order, receipt, contract, or other
- Free local AI classification with Ollama and Pydantic Structured Outputs (stage 4)
- Structured invoice field extraction with nullable missing values (stage 5)
- Strict Pydantic invoice schema and type validation (stage 6)
- Deterministic Python business-rule validation (stage 7)
- Processing statuses: `processed`, `needs_review`, and `failed` (stage 8)
- MySQL persistence for documents, extracted data, runs, and errors (stage 9)
- Duplicate prevention by SHA-256 hash and invoice identity (stage 10)
- Batch processing for all supported documents in a folder, with an aggregate
  status summary and per-file failure isolation (stage 11)
- IMAP email automation that downloads unread PDF, DOCX, and TXT attachments,
  then sends only the newly downloaded files through the pipeline (stage 12)
- Google Sheets synchronization for validated invoices and review status
  (stage 13)
- Gmail SMTP notifications for processed invoices and documents requiring
  manual review (stage 14)
- Importable n8n email-to-API workflow with attachment filtering and review
  routing (stage 15)
- FastAPI upload, document retrieval, review queue, and approval endpoints
  (stage 16)
- Rotating application logs and bounded exponential retries for transient local
  AI failures, with per-document batch isolation (stage 17)
- Docker image and Compose stack for FastAPI, MySQL, and n8n with persistent
  volumes and health-based startup ordering (stage 18)

## Run

Python 3.10 or newer is required. Install the dependencies first:

```bash
python -m pip install -r requirements.txt
```

Install [Ollama](https://ollama.com/download/windows), then download the local model:

```bash
ollama pull qwen2.5:3b
```

Copy `.env.example` to `.env`:

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
DATABASE_URL=mysql+pymysql://document_app:change_me@localhost:3306/document_automation?charset=utf8mb4
```

The model runs locally. No paid API key is required, and document text is not
sent to an external AI service.

```bash
python -m app.main path/to/invoice.pdf
```

To process every supported file in a folder:

```bash
python -m app.main path/to/documents/
```

The batch continues when an individual document fails and finishes with a
summary such as `50 received`, `43 processed`, `5 needs review`, `2 failed`.

### Email automation

Add the IMAP settings from `.env.example` to the ignored local `.env`. Use an
app password supplied by your email provider rather than your normal account
password. Then run:

```bash
python -m app.main --email
```

Only unread messages are inspected. Supported attachments are saved under
`data/email_attachments`, processed by the same validation and database
pipeline, and the source message is marked as read after a supported attachment
has been downloaded successfully.
Each run inspects at most the newest 25 unread messages by default; change
`EMAIL_MAX_MESSAGES` when a different limit is needed.

### Google Sheets integration

Create a Google Cloud service account, enable the Google Sheets API, download
its JSON key under `credentials/`, and share the destination spreadsheet with
the service account email as an Editor. Then set the three `GOOGLE_SHEETS_*`
values shown in `.env.example`. Credential JSON files and `.env` are ignored by
Git. When configured, every validated invoice is appended to the `Invoices`
worksheet with these columns:

```text
Invoice | Company | Date | Total | Currency | Status
```

### Email notifications

The pipeline sends a compact success or manual-review message after a validated
invoice is saved. For Gmail, the stage 12 username and app password are reused
automatically, and the notification goes back to that account by default. Set
the optional `SMTP_*` and `NOTIFICATION_EMAIL_TO` variables from `.env.example`
to use a different sender or recipient.

### n8n workflow

Import `n8n/workflows/email-document-pipeline.json` into n8n. It receives Gmail
messages through IMAP, keeps PDF/DOCX/TXT attachments, and uploads each file to
the Python `POST /documents` endpoint. The workflow is intentionally inactive
until stage 16 adds that API. See `n8n/README.md` for setup and duplicate-ingestion
guidance.

### FastAPI

Start the API locally:

```bash
uvicorn app.api:create_app --factory --host 0.0.0.0 --port 8000
```

Interactive documentation is available at `http://localhost:8000/docs`.

```text
POST /documents
GET  /documents
GET  /documents/{id}
GET  /review
POST /documents/{id}/approve
```

`POST /documents` accepts multipart field `file`, rejects unsupported files and
uploads larger than 20 MB, checks duplicates before AI processing, and returns
the stored status for n8n routing.

### Logs and retries

Runtime events and final errors are written to UTF-8 `logs/app.log`. The log
rotates at 5 MB and keeps three backups. Temporary Ollama request failures are
retried three times with exponential delays (`1s`, `2s`) by default. Configure
this with `AI_MAX_ATTEMPTS` and `AI_RETRY_BASE_SECONDS`. Empty or invalid model
output is treated as a data error and is not retried. A failed document remains
isolated and does not stop the rest of a batch.

### Docker Compose

Install Docker Desktop, copy `.env.docker.example` to `.env.docker`, replace all
`change_me` values, and keep the existing local `.env` for Gmail/Ollama settings.
Then run:

```bash
docker compose --env-file .env.docker up --build -d
docker compose --env-file .env.docker ps
```

Open FastAPI docs at `http://localhost:8016/docs` and n8n at
`http://localhost:5678`. MySQL is exposed on host port `3307` so it does not
conflict with an existing local MySQL on `3306`. Inside Compose, n8n reaches the
API at `http://api:8000`, while the API reaches the Windows Ollama service at
`http://host.docker.internal:11434`.

Import `/home/node/workflows/email-document-pipeline.json` in n8n and configure
the Gmail IMAP credential. Do not activate both n8n email ingestion and the
Python `--email` poller for the same inbox.

Stop containers without deleting persistent data:

```bash
docker compose --env-file .env.docker down
```

Add `-v` only when you intentionally want to delete MySQL and n8n volumes.

Example output:

```text
invoice.pdf
-> PDF detected
-> ready for processing
-> text extracted

Document text:

Invoice INV-001

Document classification:

{
  "document_type": "invoice"
}

Extracted invoice data:

{
  "invoice_number": "INV-001",
  "company_name": "Example Ltd",
  "invoice_date": "2026-09-15",
  "due_date": null,
  "currency": "USD",
  "subtotal": 1000.0,
  "tax": 250.0,
  "total": 1250.0,
  "email": "billing@example.com",
  "confidence": 0.96,
  "uncertain_fields": []
}

-> Pydantic schema validation passed
-> business rules validation passed

Status: processed
```

Business rules verify required text, positive totals, supported currencies,
email format, date order, non-negative amounts, and subtotal/tax arithmetic.
Missing required data, low confidence, uncertain fields, or failed business
rules produce `needs_review`. Technical failures produce `failed`.

## Database

The SQLAlchemy schema creates these MySQL tables:

- `documents`
- `extracted_data`
- `processing_runs`
- `errors`

Set `DATABASE_URL` to enable persistence. Database credentials belong only in
the ignored local `.env`; `.env.example` contains placeholders.

Before AI processing, the pipeline checks the file SHA-256 hash. Before saving
an invoice, it also checks the `invoice_number + company` pair. A duplicate is
reported and is not inserted a second time.

## Test

```bash
python -m unittest discover -v
```
