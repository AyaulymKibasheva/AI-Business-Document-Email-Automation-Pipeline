"""Command-line entry point for manual document uploads."""

import argparse
from collections.abc import Sequence

from app.extractor import TextExtractionError, extract_text
from app.parser import receive_document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upload a business document to the processing pipeline."
    )
    parser.add_argument("file", help="Path to a PDF, DOCX, or TXT document")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        document = receive_document(args.file)
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}")
        return 1

    print(document.filename)
    print(f"-> {document.document_type.value} detected")
    print("-> ready for processing")

    try:
        text = extract_text(document)
    except TextExtractionError as error:
        print(f"Error: {error}")
        return 1

    print("-> text extracted")
    print("\nDocument text:\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
