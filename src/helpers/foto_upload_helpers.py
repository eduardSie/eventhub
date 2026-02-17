import re

from fastapi import HTTPException

FILENAME_RE = re.compile(r"^[0-9a-fA-F-]{36}\.(jpg|png|webp|gif)$")

def validate_filename(filename: str) -> None:
    if not FILENAME_RE.fullmatch(filename or ""):
        raise HTTPException(status_code=400, detail="Invalid filename")

def ext_to_mime(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    return {
        "jpg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
    }.get(ext, "application/octet-stream")
