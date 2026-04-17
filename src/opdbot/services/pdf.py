import asyncio
import subprocess
from pathlib import Path

from loguru import logger


async def docx_to_pdf(docx_path: Path) -> Path | None:
    pdf_path = docx_path.with_suffix(".pdf")
    try:
        proc = await asyncio.create_subprocess_exec(
            "libreoffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(docx_path.parent),
            str(docx_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("LibreOffice conversion failed: {}", stderr.decode())
            return None
        return pdf_path if pdf_path.exists() else None
    except FileNotFoundError:
        logger.warning("LibreOffice not found, PDF conversion skipped")
        return None
