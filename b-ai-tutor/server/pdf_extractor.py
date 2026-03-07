"""
PDF extraction utilities.

Uses pdfplumber to pull plain text and metadata from PDF files.
All public functions are pure (no side effects beyond reading the file)
and raise on unexpected errors so callers can decide how to handle them.
"""

import logging

import pdfplumber

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract all readable text from a PDF file.

    Iterates over every page and concatenates the text, inserting a newline
    between pages.  Pages that yield no text (e.g. scanned images without
    an OCR layer) are silently skipped.

    Args:
        pdf_path: Absolute or relative path to the PDF file.

    Returns:
        A single string containing all extracted text, stripped of leading /
        trailing whitespace.  Returns an empty string if no text was found.

    Raises:
        Exception: Wraps any pdfplumber error with a descriptive message.
    """
    logger.info("Extracting text from PDF: %s", pdf_path)
    text_parts: list[str] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            logger.debug("PDF has %d page(s).", total_pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                    logger.debug(
                        "Page %d/%d: extracted %d characters.",
                        page_num,
                        total_pages,
                        len(page_text),
                    )
                else:
                    logger.debug("Page %d/%d: no text found (possibly image-only).", page_num, total_pages)

    except Exception as exc:
        logger.exception("Failed to extract text from PDF '%s': %s", pdf_path, exc)
        raise Exception(f"Error extracting text from PDF: {exc}") from exc

    extracted = "\n".join(text_parts).strip()
    logger.info(
        "Text extraction complete: %d character(s) from %d page(s).",
        len(extracted),
        len(text_parts),
    )
    return extracted


def extract_pdf_metadata(pdf_path: str) -> dict:
    """
    Extract metadata from a PDF file.

    Reads the document-level metadata (author, title, creation date, etc.)
    as exposed by pdfplumber / PyPDF2 and also returns the total page count.

    Args:
        pdf_path: Absolute or relative path to the PDF file.

    Returns:
        A dict with at least:
            - "total_pages" (int) : number of pages in the document
            - "metadata"    (dict): raw PDF metadata fields (may be empty)
        On error, returns {"error": "<message>"} instead of raising, so that
        callers can still proceed with partial data.
    """
    logger.info("Extracting metadata from PDF: %s", pdf_path)
    try:
        with pdfplumber.open(pdf_path) as pdf:
            result = {
                "total_pages": len(pdf.pages),
                "metadata": pdf.metadata or {},
            }
            logger.debug(
                "Metadata extracted: %d page(s), fields=%s.",
                result["total_pages"],
                list(result["metadata"].keys()),
            )
            return result

    except Exception as exc:
        logger.exception("Failed to extract metadata from PDF '%s': %s", pdf_path, exc)
        return {"error": str(exc)}
