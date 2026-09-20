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
