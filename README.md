# PDF Image Replacement Backend

This FastAPI backend provides endpoints for uploading PDFs, listing page images, previewing pages, and replacing images precisely within a PDF document while preserving layout.

## Endpoints

- `POST /upload` - Upload a PDF file.
- `GET /preview` - Retrieve a base64 preview for a specific page.
- `GET /images` - List images detected on a page along with bounding boxes.
- `POST /replace` - Replace a selected image on a page with a new uploaded image.
- `GET /health` - Health check endpoint.

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
