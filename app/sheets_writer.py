"""Append processed invoice data to Google Sheets."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import gspread
from dotenv import load_dotenv

from app.validator import Invoice

SHEET_HEADERS = ["Invoice", "Company", "Date", "Total", "Currency", "Status"]


class GoogleSheetsError(RuntimeError):
    """Raised when Google Sheets configuration or synchronization fails."""


@dataclass(frozen=True)
class GoogleSheetsConfig:
    """Configuration required for unattended service-account access."""

    credentials_file: Path
    spreadsheet_id: str
    worksheet: str = "Invoices"

    @classmethod
    def from_env(cls) -> "GoogleSheetsConfig | None":
        load_dotenv()
        values = {
            "GOOGLE_SHEETS_CREDENTIALS_FILE": os.getenv(
                "GOOGLE_SHEETS_CREDENTIALS_FILE"
            ),
            "GOOGLE_SHEETS_SPREADSHEET_ID": os.getenv(
                "GOOGLE_SHEETS_SPREADSHEET_ID"
            ),
        }
        if not any(values.values()):
            return None
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise GoogleSheetsError(
                "Missing Google Sheets settings: " + ", ".join(missing)
            )
        credentials_file = Path(values["GOOGLE_SHEETS_CREDENTIALS_FILE"] or "")
        if not credentials_file.is_file():
            raise GoogleSheetsError(
                f"Google service-account file not found: {credentials_file}"
            )
        return cls(
            credentials_file=credentials_file,
            spreadsheet_id=values["GOOGLE_SHEETS_SPREADSHEET_ID"] or "",
            worksheet=os.getenv("GOOGLE_SHEETS_WORKSHEET", "Invoices"),
        )


def append_invoice_row(
    config: GoogleSheetsConfig,
    invoice: Invoice,
    status: str,
    *,
    client_factory: Callable[..., Any] = gspread.service_account,
) -> None:
    """Create the configured worksheet if needed and append one invoice row."""

    try:
        client = client_factory(filename=str(config.credentials_file))
        spreadsheet = client.open_by_key(config.spreadsheet_id)
        try:
            worksheet = spreadsheet.worksheet(config.worksheet)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=config.worksheet, rows=1000, cols=len(SHEET_HEADERS)
            )
        if not worksheet.row_values(1):
            worksheet.update("A1:F1", [SHEET_HEADERS])
        worksheet.append_row(
            [
                invoice.invoice_number,
                invoice.company_name,
                invoice.invoice_date.isoformat(),
                float(invoice.total),
                invoice.currency,
                status,
            ],
            value_input_option="USER_ENTERED",
        )
    except GoogleSheetsError:
        raise
    except Exception as error:
        raise GoogleSheetsError(f"Google Sheets synchronization failed: {error}") from error
