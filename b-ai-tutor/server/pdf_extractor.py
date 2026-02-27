import pdfplumber
from typing import Tuple


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract all text from a PDF file
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text from the PDF
    """
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        raise Exception(f"Error extracting text from PDF: {str(e)}")
    
    return text.strip()


def extract_pdf_metadata(pdf_path: str) -> dict:
    """
    Extract metadata from a PDF file
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dictionary with PDF metadata
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return {
                "total_pages": len(pdf.pages),
                "metadata": pdf.metadata
            }
    except Exception as e:
        return {"error": str(e)}
