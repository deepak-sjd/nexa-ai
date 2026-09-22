import os
import re
import uuid
from collections.abc import Iterable
from pathlib import Path

from app.core.config import settings
from app.core.logging_config import get_logger


logger = get_logger(__name__)


# Where the API serves stored images from (see routes/images.py).
# Kept here so the route and the response schema can't drift apart.
IMAGES_ROUTE_PREFIX = "/api/v1/images/files"


_EXTENSION_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

# Filenames we generate are always 32 hex chars + a known extension.
# Anything else is rejected before it can touch the filesystem —
# this is what makes "../../etc/passwd" style requests impossible.
_SAFE_FILENAME = re.compile(r"[a-f0-9]{32}\.(?:png|jpg|webp|gif)")


def image_public_path(filename: str) -> str:
    """URL path (relative to the API host) for a stored image."""

    return f"{IMAGES_ROUTE_PREFIX}/{filename}"


def _images_dir() -> Path:
    directory = Path(settings.generated_images_dir)
    directory.mkdir(parents=True, exist_ok=True)

    return directory


def save_image(image_bytes: bytes, mime_type: str) -> str:
    """
    Store image bytes and return the generated filename.

    Written to a temp file first and then renamed, so a request
    for the image can never observe a half-written file.
    """

    extension = _EXTENSION_BY_MIME.get(
        (mime_type or "").lower(),
        ".png",
    )

    directory = _images_dir()

    filename = f"{uuid.uuid4().hex}{extension}"

    final_path = directory / filename
    temp_path = directory / f".{filename}.tmp"

    try:
        temp_path.write_bytes(image_bytes)
        os.replace(temp_path, final_path)
    finally:
        temp_path.unlink(missing_ok=True)

    return filename


def resolve_image_file(filename: str) -> Path | None:
    """
    Map a requested filename to a file on disk, or None.

    None for anything that isn't a filename this service could
    have generated, or that doesn't exist.
    """

    if not _SAFE_FILENAME.fullmatch(filename or ""):
        return None

    path = _images_dir() / filename

    return path if path.is_file() else None


def delete_image_files(filenames: Iterable[str | None]) -> None:
    """
    Best-effort removal. Never raises — a leftover file is an
    annoyance, but failing a user's delete request over it would
    be worse.
    """

    for filename in filenames:

        if not filename or not _SAFE_FILENAME.fullmatch(filename):
            continue

        try:
            (_images_dir() / filename).unlink(missing_ok=True)
        except OSError as error:
            logger.warning(
                "Could not delete image file %s: %s",
                filename,
                error,
            )
