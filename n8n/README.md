# n8n workflow

Import `workflows/email-document-pipeline.json` into n8n. The workflow is
deliberately inactive until stage 16 exposes `POST /documents`.

## Setup

1. Import the workflow JSON in n8n.
2. Open **Gmail IMAP Trigger** and create an IMAP credential:
   - host: `imap.gmail.com`
   - port: `993`
   - SSL/TLS: enabled
   - username: Gmail address
   - password: Google app password (never the normal account password)
3. Keep the workflow inactive until `http://host.docker.internal:8000/documents`
   responds successfully after stage 16.
4. Run one manual test with an unread email containing a PDF, DOCX, or TXT.
5. Activate the workflow only after the test succeeds.

The Code node creates one n8n item per supported attachment. The HTTP Request
node uploads each item as multipart field `file` and includes `source=email`.
The response is routed to separate processed and manual-review branches. The
Python application remains responsible for AI extraction, validation, MySQL,
Google Sheets, and email notifications.

Do not enable both the Python `--email` poller and the n8n IMAP trigger for the
same inbox. Choose one email-ingestion owner to avoid duplicate processing.
