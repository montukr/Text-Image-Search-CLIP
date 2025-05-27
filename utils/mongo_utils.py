"""
MongoDB + GridFS helpers
------------------------
• save_image()   – stores original + thumbnail (height 220 px) with EXIF orientation fix
• load_image()   – fetch original as PIL.Image
• load_thumb()   – fetch thumbnail; auto-creates on demand
• all_filenames()– generator of original filenames (no _thumb suffix)
• move_to_trash()– soft delete by adding _deleted suffix
• restore_from_trash()– restore from trash by removing _deleted suffix
• permanently_delete()– hard delete from database
• all_trash_filenames()– generator of trashed filenames
"""

import os, io, base64
from typing import Generator, Optional
from pymongo import MongoClient
import gridfs
from PIL import Image, ExifTags

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
DELETED_SUFFIX = "_deleted"
THUMB_HEIGHT = 220  # px

def _fix_orientation(img: Image.Image) -> Image.Image:
    """
    Fix image orientation based on EXIF data.
    Many cameras store orientation info in EXIF but don't rotate the actual image data.
    """
    try:
        # Get EXIF data
        exif = img._getexif()
        if exif is None:
            return img

        # Find orientation tag
        orientation_key = None
        for key in ExifTags.TAGS.keys():
            if ExifTags.TAGS[key] == 'Orientation':
                orientation_key = key
                break

        if orientation_key is None or orientation_key not in exif:
            return img

        orientation = exif[orientation_key]

        # Apply rotation based on orientation value
        if orientation == 2:
            # Horizontal flip
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            # 180 degree rotation
            img = img.rotate(180, expand=True)
        elif orientation == 4:
            # Vertical flip
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        elif orientation == 5:
            # Horizontal flip + 90 degree rotation
            img = img.transpose(Image.FLIP_LEFT_RIGHT).rotate(90, expand=True)
        elif orientation == 6:
            # 90 degree rotation
            img = img.rotate(270, expand=True)
        elif orientation == 7:
            # Horizontal flip + 270 degree rotation
            img = img.transpose(Image.FLIP_LEFT_RIGHT).rotate(270, expand=True)
        elif orientation == 8:
            # 270 degree rotation
            img = img.rotate(90, expand=True)

        return img

    except (AttributeError, KeyError, TypeError):
        # If there's any issue with EXIF data, return original image
        return img

def _thumbnail(img: Image.Image) -> Image.Image:
    im = img.copy()
    im.thumbnail((9999, THUMB_HEIGHT))   # preserve aspect ratio
    return im

def _put_file(data: bytes, filename: str) -> None:
    prev = fs.find_one({"filename": filename})
    if prev:
        fs.delete(prev._id)
    fs.put(data, filename=filename)

def _is_deleted(filename: str) -> bool:
    """Check if filename is in trash (has _deleted suffix)"""
    return filename.endswith(DELETED_SUFFIX)

def _get_original_name(filename: str) -> str:
    """Remove _deleted suffix to get original name"""
    if _is_deleted(filename):
        return filename.replace(DELETED_SUFFIX, "")
    return filename

def _get_deleted_name(filename: str) -> str:
    """Add _deleted suffix to filename"""
    return f"{filename}{DELETED_SUFFIX}"

# ------------------------------------------------------------------
# Public helpers
# ------------------------------------------------------------------
def save_image(file_like, filename: str) -> None:
    """
    Save original file *filename* and a PNG thumbnail <filename>_thumb.
    Automatically fixes EXIF orientation issues.
    """
    # ---- Read and fix orientation ----
    file_like.seek(0)
    data = file_like.read()

    # Load image and fix orientation
    img = Image.open(io.BytesIO(data))
    img = _fix_orientation(img)

    # Convert to RGB if necessary (removes alpha channel, fixes some format issues)
    if img.mode in ('RGBA', 'LA', 'P'):
        # Create white background for transparency
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # ---- Save corrected original ----
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)  # High quality for original
    _put_file(buf.getvalue(), filename)

    # ---- Create and save thumbnail ----
    thumb = _thumbnail(img)
    thumb_buf = io.BytesIO()
    thumb.save(thumb_buf, format="PNG")  # PNG for thumbnail (lossless, good for small images)
    _put_file(thumb_buf.getvalue(), f"{filename}{THUMB_SUFFIX}")

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
    """Yield every *original* filename (exclude thumbnails and deleted files)."""
    for g in fs.find():
        if not g.filename.endswith(THUMB_SUFFIX) and not _is_deleted(g.filename):
            yield g.filename

def move_to_trash(filename: str) -> bool:
    """
    Soft delete: rename original and thumbnail with _deleted suffix.
    Returns True if successful, False if file not found.
    """
    # Check if original file exists
    orig_file = fs.find_one({"filename": filename})
    if not orig_file:
        return False

    # Move original file to trash
    orig_data = orig_file.read()
    deleted_name = _get_deleted_name(filename)
    _put_file(orig_data, deleted_name)
    fs.delete(orig_file._id)

    # Move thumbnail to trash if it exists
    thumb_name = f"{filename}{THUMB_SUFFIX}"
    thumb_file = fs.find_one({"filename": thumb_name})
    if thumb_file:
        thumb_data = thumb_file.read()
        deleted_thumb_name = f"{deleted_name}{THUMB_SUFFIX}"
        _put_file(thumb_data, deleted_thumb_name)
        fs.delete(thumb_file._id)

    return True

def restore_from_trash(filename: str) -> bool:
    """
    Restore from trash: remove _deleted suffix from original and thumbnail.
    Returns True if successful, False if file not found in trash.
    """
    deleted_name = _get_deleted_name(filename)

    # Check if deleted file exists
    deleted_file = fs.find_one({"filename": deleted_name})
    if not deleted_file:
        return False

    # Restore original file
    orig_data = deleted_file.read()
    _put_file(orig_data, filename)
    fs.delete(deleted_file._id)

    # Restore thumbnail if it exists
    deleted_thumb_name = f"{deleted_name}{THUMB_SUFFIX}"
    deleted_thumb = fs.find_one({"filename": deleted_thumb_name})
    if deleted_thumb:
        thumb_data = deleted_thumb.read()
        thumb_name = f"{filename}{THUMB_SUFFIX}"
        _put_file(thumb_data, thumb_name)
        fs.delete(deleted_thumb._id)

    return True

def permanently_delete(filename: str) -> bool:
    """
    Permanently delete file from trash.
    Returns True if successful, False if file not found in trash.
    """
    deleted_name = _get_deleted_name(filename)

    # Delete original file from trash
    deleted_file = fs.find_one({"filename": deleted_name})
    if not deleted_file:
        return False

    fs.delete(deleted_file._id)

    # Delete thumbnail from trash if it exists
    deleted_thumb_name = f"{deleted_name}{THUMB_SUFFIX}"
    deleted_thumb = fs.find_one({"filename": deleted_thumb_name})
    if deleted_thumb:
        fs.delete(deleted_thumb._id)

    return True

def all_trash_filenames() -> Generator[str, None, None]:
    """Yield every filename in trash (original names without _deleted suffix)."""
    for g in fs.find():
        if _is_deleted(g.filename) and not g.filename.endswith(f"{THUMB_SUFFIX}{DELETED_SUFFIX}"):
            # Return original name without _deleted suffix
            yield _get_original_name(g.filename)

def load_deleted_image(filename: str) -> Optional[Image.Image]:
    """Return full-size PIL.Image from trash or None."""
    deleted_name = _get_deleted_name(filename)
    grid_out = fs.find_one({"filename": deleted_name})
    if grid_out:
        return Image.open(io.BytesIO(grid_out.read()))
    return None

def load_deleted_thumb(filename: str) -> Optional[Image.Image]:
    """Return thumbnail PIL.Image from trash."""
    deleted_name = _get_deleted_name(filename)
    deleted_thumb_name = f"{deleted_name}{THUMB_SUFFIX}"
    grid_out = fs.find_one({"filename": deleted_thumb_name})

    if grid_out:
        return Image.open(io.BytesIO(grid_out.read()))

    # Fallback – load from deleted original if thumb doesn't exist
    orig = load_deleted_image(filename)
    if orig is None:
        return None
    return _thumbnail(orig)
