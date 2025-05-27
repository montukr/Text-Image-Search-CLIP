"""
MongoDB + GridFS helpers
------------------------
• save_image()   – stores original + thumbnail (height 220 px)
• load_image()   – fetch original as PIL.Image
• load_thumb()   – fetch thumbnail; auto-creates on demand
• all_filenames()– generator of original filenames (no _thumb suffix)
"""

import os, io, base64
from typing import Generator, Optional
from pymongo import MongoClient
import gridfs
from PIL import Image

# ------------------------------------------------------------------
# Mongo connection (URI can be overridden with MONGO_URI env var)
# ------------------------------------------------------------------
client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
db     = client["image_db"]
fs     = gridfs.GridFS(db)

# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------
THUMB_SUFFIX = "_thumb"
THUMB_HEIGHT = 220  # px

def _thumbnail(img: Image.Image) -> Image.Image:
    im = img.copy()
    im.thumbnail((9999, THUMB_HEIGHT))   # preserve aspect ratio
    return im

def _put_file(data: bytes, filename: str) -> None:
    prev = fs.find_one({"filename": filename})
    if prev:
        fs.delete(prev._id)
    fs.put(data, filename=filename)

# ------------------------------------------------------------------
# Public helpers
# ------------------------------------------------------------------
def save_image(file_like, filename: str) -> None:
    """
    Save original file *filename* and a PNG thumbnail <filename>_thumb.
    """
    # ---- original ----
    file_like.seek(0)
    data = file_like.read()
    _put_file(data, filename)

    # ---- thumbnail ----
    img = Image.open(io.BytesIO(data)).convert("RGB")
    thumb = _thumbnail(img)

    buf = io.BytesIO()
    thumb.save(buf, format="PNG")        # lossless, tiny for thumb
    _put_file(buf.getvalue(), f"{filename}{THUMB_SUFFIX}")

def load_image(filename: str) -> Optional[Image.Image]:
    """Return full-size PIL.Image or None."""
    grid_out = fs.find_one({"filename": filename})
    if grid_out:
        return Image.open(io.BytesIO(grid_out.read()))
    return None

def load_thumb(filename: str) -> Optional[Image.Image]:
    """Return thumbnail PIL.Image; create & cache if missing."""
    thumb_name = f"{filename}{THUMB_SUFFIX}"
    grid_out = fs.find_one({"filename": thumb_name})

    if grid_out:
        return Image.open(io.BytesIO(grid_out.read()))

    # Fallback – create on the fly, cache, then return
    orig = load_image(filename)
    if orig is None:
        return None
    thumb = _thumbnail(orig)
    buf = io.BytesIO()
    thumb.save(buf, format="PNG")
    _put_file(buf.getvalue(), thumb_name)
    return thumb

def all_filenames() -> Generator[str, None, None]:
    """Yield every *original* filename (exclude thumbnails)."""
    for g in fs.find():
        if not g.filename.endswith(THUMB_SUFFIX):
            yield g.filename
