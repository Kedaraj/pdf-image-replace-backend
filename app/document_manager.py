"""Utility helpers for storing PDFs and performing image replacements."""

from __future__ import annotations

import base64
import io
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import fitz  # PyMuPDF
from PIL import Image


@dataclass
class PageImage:
    index: int
    bbox: Tuple[float, float, float, float]
    width: int
    height: int
    xref: int
    preview_base64: str
    extension: str


class DocumentManager:
    """Handles persistence and mutation of uploaded PDFs."""

    def __init__(self, storage_root: Path) -> None:
        self.storage_root = storage_root
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def _document_path(self, doc_id: str) -> Path:
        return self.storage_root / f"{doc_id}.pdf"

    def _ensure_document(self, doc_id: str) -> Path:
        path = self._document_path(doc_id)
        if not path.exists():
            raise FileNotFoundError("Document not found")
        return path

    def get_pdf_file(self, doc_id: str) -> Path:
        """Return the path to the stored PDF, ensuring it exists."""
        return self._ensure_document(doc_id)

    @staticmethod
    def _pixmap_from_bytes(raw_bytes: bytes) -> fitz.Pixmap:
        with Image.open(io.BytesIO(raw_bytes)) as pil_img:
            if pil_img.mode not in {"RGB", "RGBA"}:
                pil_img = pil_img.convert("RGBA")

            if pil_img.mode == "RGBA":
                samples = pil_img.tobytes()
                pix = fitz.Pixmap(
                    fitz.csRGBA, pil_img.width, pil_img.height, samples
                )
            else:
                samples = pil_img.convert("RGB").tobytes()
                pix = fitz.Pixmap(
                    fitz.csRGB, pil_img.width, pil_img.height, samples
                )

        return pix

    def save_pdf(self, file_bytes: bytes) -> Tuple[str, int]:
        doc_id = uuid.uuid4().hex
        path = self._document_path(doc_id)
        path.write_bytes(file_bytes)

        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            page_count = doc.page_count

        return doc_id, page_count

    def get_page_preview(
        self, doc_id: str, page_number: int, zoom: float = 2.0
    ) -> Tuple[str, float, float]:
        path = self._ensure_document(doc_id)

        with fitz.open(path) as doc:
            if not 1 <= page_number <= doc.page_count:
                raise ValueError("Invalid page number")

            page = doc.load_page(page_number - 1)
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            preview_b64 = base64.b64encode(pix.tobytes("png")).decode("utf-8")
            rect = page.rect
            return preview_b64, rect.width, rect.height

    def list_page_images(
        self, doc_id: str, page_number: int
    ) -> Tuple[List[PageImage], Tuple[float, float]]:
        with fitz.open(self._ensure_document(doc_id)) as doc:
            if not 1 <= page_number <= doc.page_count:
                raise ValueError("Invalid page number")

            page = doc.load_page(page_number - 1)
            page_rect = page.rect
            images: List[PageImage] = []

            counter = 0
            for image_entry in page.get_images(full=True):
                xref = image_entry[0]
                rects = page.get_image_rects(xref)
                if not rects:
                    # Skip images with no drawable rects (e.g., masks)
                    continue

                if not doc.xref_is_image(xref):
                    continue

                try:
                    image_info = doc.extract_image(xref)
                except RuntimeError:
                    continue

                if not isinstance(image_info, dict) or "image" not in image_info:
                    continue

                preview = base64.b64encode(image_info.get("image", b""))
                for rect in rects:
                    bbox = (rect.x0, rect.y0, rect.x1, rect.y1)
                    images.append(
                        PageImage(
                            index=counter,
                            bbox=bbox,
                            width=image_info.get("width", 0),
                            height=image_info.get("height", 0),
                            xref=xref,
                            preview_base64=preview.decode("utf-8"),
                            extension=image_info.get("ext", "png"),
                        )
                    )
                    counter += 1

            return images, (page_rect.width, page_rect.height)

    def replace_page_image(
        self,
        doc_id: str,
        page_number: int,
        image_index: int,
        new_image_bytes: bytes,
    ) -> None:
        path = self._ensure_document(doc_id)

        images, _ = self.list_page_images(doc_id, page_number)
        target = next((img for img in images if img.index == image_index), None)
        if target is None:
            raise ValueError("Image index not found on page")

        pix = self._pixmap_from_bytes(new_image_bytes)

        with fitz.open(path) as doc:
            page = doc.load_page(page_number - 1)
            page.replace_image(target.xref, pixmap=pix)
            doc.save(path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)

        pix = None
