from pathlib import Path


def extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        import fitz

        return "\n".join(page.get_text() for page in fitz.open(path))
    if path.suffix.lower() == ".docx":
        from docx import Document

        return "\n".join(p.text for p in Document(path).paragraphs)
    if path.suffix.lower() == ".tex":
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError("Only PDF, DOCX, and TEX resumes are supported")
