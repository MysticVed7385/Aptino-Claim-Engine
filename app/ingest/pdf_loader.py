from pathlib import Path
from typing import TypedDict

import fitz


class PageText(TypedDict):
    page_number: int
    text: str


def load_policy_pdf(pdf_path: str) -> list[PageText]:
    """
    Extract text from every page of the policy PDF.

    Page numbers are 1-based so that they match the PDF
    pages shown to a reviewer.
    """
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"Policy PDF not found: {path}")

    pages: list[PageText] = []

    with fitz.open(path) as document:
        for page_index, page in enumerate(document):
            text = page.get_text("text").strip()

            if text:
                pages.append(
                    {
                        "page_number": page_index + 1,
                        "text": text,
                    }
                )

    if not pages:
        raise ValueError("No text could be extracted from the policy PDF.")

    return pages