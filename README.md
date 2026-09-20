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

## Run

Python 3.10 or newer is required. Install the dependencies first:

```bash
python -m pip install -r requirements.txt
```

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
```

## Test

```bash
python -m unittest discover -v
```
