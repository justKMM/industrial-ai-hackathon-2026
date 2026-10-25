"""Uploaded documents to the case folder the pipeline reads.

`ai_agent.inputs.find_inputs` wants one text specification (`spec.md`) and one image. The browser sends any number of files, so:

  * text files (Markdown or plain text, UTF-8) become `spec.md`: one file as it is, several joined in upload order under a heading each
  * the first image becomes `drawing.<ext>`; a second one is refused
  * the kind of a file is decided by its content (magic bytes, then a strict UTF-8 decode), never by its name or its declared type
  * a file name is only ever used as a heading inside `spec.md`, after it has been cleaned; it never becomes a path
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from backend.settings import MAX_FILE_BYTES, MAX_FILES, MAX_TEXT_CHARS

IMAGE_MAGIC = ((b"\x89PNG\r\n\x1a\n", "png"), (b"\xff\xd8\xff", "jpg"))


class UploadError(Exception):
    """A refused upload: `status` is the HTTP status, `detail` the message the user sees."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass
class Prepared:
    spec_text: str | None = None
    image: bytes | None = None
    image_ext: str | None = None
    files: list[dict] = field(default_factory=list)  # what the job remembers: name, role, bytes

    def write(self, case_dir: Path) -> None:
        """Write the case folder the pipeline reads."""
        case_dir.mkdir(parents=True, exist_ok=True)
        if self.spec_text is not None:
            (case_dir / "spec.md").write_text(self.spec_text, encoding="utf-8")
        if self.image is not None:
            (case_dir / f"drawing.{self.image_ext}").write_bytes(self.image)


def clean_name(name: str) -> str:
    """A file name safe to print in a heading: no path, no control characters, no markup, at most 80 characters."""
    base = re.split(r"[\\/]", name or "file")[-1]
    return re.sub(r"[^\w .()\-]+", "_", base).strip(" ._")[:80] or "file"


def image_extension(data: bytes) -> str | None:
    for magic, ext in IMAGE_MAGIC:
        if data.startswith(magic):
            return ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _check_image(name: str, data: bytes) -> None:
    try:
        from PIL import Image
    except ImportError:  # the signature has been checked; Pillow is only a second opinion
        return
    try:
        with Image.open(io.BytesIO(data)) as picture:
            picture.verify()
    except Exception:
        raise UploadError(400, f"{name}: the image is damaged or cannot be read.") from None


def _decode_text(name: str, data: bytes) -> str:
    if b"\x00" in data:
        raise UploadError(415, f"{name}: this file is not text. Use Markdown or text for the specification, PNG, JPG or WebP for the drawing.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise UploadError(415, f"{name}: the text is not UTF-8. Save it as UTF-8 and upload it again.") from None
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def prepare(files: list[tuple[str, bytes]]) -> Prepared:
    """Sort the uploaded (name, content) pairs into a specification and a drawing, or refuse them with an `UploadError`."""
    if not files:
        raise UploadError(400, "No file was uploaded. Add a specification and, if you have one, a drawing.")
    if len(files) > MAX_FILES:
        raise UploadError(400, f"At most {MAX_FILES} files can be uploaded at once.")

    result = Prepared()
    texts: list[tuple[str, str]] = []
    for name, data in files:
        shown = clean_name(name)
        if not data:
            raise UploadError(400, f"{shown}: the file is empty.")
        if len(data) > MAX_FILE_BYTES:
            raise UploadError(413, f"{shown}: larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.")
        ext = image_extension(data)
        if ext:
            if result.image is not None:
                raise UploadError(400, f"{shown}: only one drawing is used. Remove the other image first.")
            _check_image(shown, data)
            result.image, result.image_ext = data, ext
            result.files.append({"name": shown, "role": "drawing", "bytes": len(data)})
        elif data.startswith(b"%PDF") or data.startswith(b"PK\x03\x04"):
            raise UploadError(415, f"{shown}: PDF and Word files are not supported yet. Use Markdown or text for the specification.")
        else:
            texts.append((shown, _decode_text(shown, data)))
            result.files.append({"name": shown, "role": "specification", "bytes": len(data)})

    texts = [(name, text) for name, text in texts if text]
    if texts:
        joined = texts[0][1] if len(texts) == 1 else "\n\n".join(f"## {name}\n\n{text}" for name, text in texts)
        if len(joined) > MAX_TEXT_CHARS:
            raise UploadError(413, f"The text files together are longer than {MAX_TEXT_CHARS:,} characters.")
        result.spec_text = joined + "\n"
    if result.spec_text is None and result.image is None:
        raise UploadError(400, "The uploaded text files are empty. Add a specification or a drawing.")
    return result
