"""FastAPI application providing PDF image replacement endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .document_manager import DocumentManager
from .schemas import (
    PageImagesResponse,
    PagePreviewResponse,
    ReplaceImageResponse,
    UploadResponse,
)

app = FastAPI(title="PDF Image Replacement API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage_dir = Path(__file__).resolve().parent.parent / "storage"
document_manager = DocumentManager(storage_dir)


@app.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)) -> UploadResponse:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_bytes = await file.read()
    doc_id, page_count = document_manager.save_pdf(file_bytes)
    return UploadResponse(document_id=doc_id, page_count=page_count)


@app.get("/preview", response_model=PagePreviewResponse)
def get_page_preview(
    document_id: str, page_number: int, zoom: float = 2.0, response: Response = None
) -> PagePreviewResponse:
    try:
        preview_base64, width, height = document_manager.get_page_preview(
            document_id, page_number, zoom=zoom
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    data_url = f"data:image/png;base64,{preview_base64}"
    if response is not None:
        response.headers["Cache-Control"] = "no-store"
    return PagePreviewResponse(
        document_id=document_id,
        page_number=page_number,
        width=width,
        height=height,
        preview_data_url=data_url,
    )


@app.get("/images", response_model=PageImagesResponse)
def list_page_images(
    document_id: str, page_number: int, response: Response = None
) -> PageImagesResponse:
    try:
        images, (width, height) = document_manager.list_page_images(
            document_id, page_number
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if response is not None:
        response.headers["Cache-Control"] = "no-store"

    return PageImagesResponse(
        document_id=document_id,
        page_number=page_number,
        width=width,
        height=height,
        images=[
            {
                "index": img.index,
                "bbox": list(img.bbox),
                "width": img.width,
                "height": img.height,
                "preview_data_url": f"data:image/{img.extension};base64,{img.preview_base64}",
            }
            for img in images
        ],
    )


@app.post("/replace", response_model=ReplaceImageResponse)
async def replace_image(
    document_id: str,
    page_number: int,
    image_index: int,
    file: UploadFile = File(...),
) -> ReplaceImageResponse:
    if file.content_type not in ("image/png", "image/jpeg", "image/jpg", "image/webp"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported")

    new_bytes = await file.read()
    try:
        document_manager.replace_page_image(document_id, page_number, image_index, new_bytes)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ReplaceImageResponse(
        document_id=document_id,
        page_number=page_number,
        image_index=image_index,
    )


@app.get("/document/{document_id}")
def download_document(document_id: str) -> FileResponse:
    try:
        pdf_path = document_manager.get_pdf_file(document_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"pdf-image-surgeon-{document_id}.pdf",
    )


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
