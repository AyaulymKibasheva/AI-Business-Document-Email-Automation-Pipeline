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
- Strict Pydantic Structured Output from the OpenAI Responses API (stage 4)

## Run

Python 3.10 or newer is required. Install the dependencies first:

```bash
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your OpenAI API key:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-5.6-terra
```

The `.env` file is ignored by Git and must never be committed.

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
```

## Test

```bash
python -m unittest discover -v
```
