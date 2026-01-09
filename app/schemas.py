"""Pydantic schemas for the PDF image replacement API."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    document_id: str = Field(..., description="Unique identifier for the stored PDF")
    page_count: int = Field(..., description="Number of pages detected in the PDF")


class PagePreviewResponse(BaseModel):
    document_id: str
    page_number: int
    width: float
    height: float
    preview_data_url: str


class PageImageMetadata(BaseModel):
    index: int
    bbox: List[float] = Field(..., description="Bounding box of the image on the page")
    width: int
    height: int
    preview_data_url: str


class PageImagesResponse(BaseModel):
    document_id: str
    page_number: int
    width: float
    height: float
    images: List[PageImageMetadata]


class ReplaceImageResponse(BaseModel):
    document_id: str
    page_number: int
    image_index: int
    status: str = Field(default="success")
