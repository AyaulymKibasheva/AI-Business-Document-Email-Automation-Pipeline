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

## Run

Python 3.10 or newer is required. No third-party dependencies are needed yet.

```bash
python -m app.main path/to/invoice.pdf
```

Example output:

```text
invoice.pdf
-> PDF detected
-> ready for processing
```

## Test

```bash
python -m unittest discover -v
```
