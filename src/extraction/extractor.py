"""Text extraction from media files (PDF, images)."""

from pathlib import Path

import pytesseract
from PIL import Image
from pypdf import PdfReader


class TextExtractor:
    """Extract text from PDF and image files."""

    # Supported extensions
    PDF_EXTENSIONS = {".pdf"}
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}

    def __init__(self, tesseract_lang: str = "rus+eng") -> None:
        self._lang = tesseract_lang

    def can_extract(self, path: Path) -> bool:
        """Check if file type is supported for extraction."""
        suffix = path.suffix.lower()
        return suffix in self.PDF_EXTENSIONS or suffix in self.IMAGE_EXTENSIONS

    def extract(self, path: Path) -> str | None:
        """
        Extract text from file.

        Returns:
            Extracted text or None if extraction failed/unsupported.
        """
        if not path.exists():
            return None

        suffix = path.suffix.lower()

        if suffix in self.PDF_EXTENSIONS:
            return self._extract_pdf(path)
        elif suffix in self.IMAGE_EXTENSIONS:
            return self._extract_image(path)

        return None

    def _extract_pdf(self, path: Path) -> str | None:
        """Extract text from PDF."""
        try:
            reader = PdfReader(path)
            texts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    texts.append(text.strip())
            return "\n\n".join(texts) if texts else None
        except Exception:
            return None

    def _extract_image(self, path: Path) -> str | None:
        """Extract text from image using OCR."""
        try:
            image = Image.open(path)
            text = pytesseract.image_to_string(image, lang=self._lang)
            return text.strip() if text.strip() else None
        except Exception:
            return None
