"""
main.py – embedding helpers & CLI bulk-embed
--------------------------------------------
Imports cleanly into Streamlit, but can also be run standalone:

    python main.py
"""
import numpy as np
import chromadb
from chromadb.utils.embedding_functions import OpenCLIPEmbeddingFunction
from utils.mongo_utils import all_filenames, load_image

# ---------------------------------------------------------------
# Chroma collection
# ---------------------------------------------------------------
client = chromadb.PersistentClient(path="./image_vecs_db")
collection = client.get_or_create_collection(
    name="image_vecs",
    embedding_function=OpenCLIPEmbeddingFunction()
)

# ---------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------
def embed_image(fid: str, pil_img) -> None:
    """Add or replace a single image in Chroma."""
    collection.add(ids=[fid], images=[np.array(pil_img)])

def remove_image_vector(fid: str) -> bool:
    """Remove image vector from ChromaDB. Returns True if successful."""
    try:
        # Check if the image exists in the collection
        existing = collection.get(ids=[fid])
        if existing['ids']:
            collection.delete(ids=[fid])
            return True
        return False
    except Exception as e:
        print(f"Error removing vector for {fid}: {e}")
        return False

def embed_all_from_mongo() -> None:
    """Index anything in MongoDB that isn't in Chroma yet."""
    for fid in all_filenames():
        existing = collection.get(ids=[fid])
        if not existing['ids']:  # If not found in collection
            img = load_image(fid)
            if img is not None:
                embed_image(fid, img)

def cleanup_orphaned_vectors() -> int:
    """Remove vectors from ChromaDB that no longer have corresponding images in MongoDB."""
    # Get all vector IDs from ChromaDB
    all_vectors = collection.get()
    vector_ids = set(all_vectors['ids'])

    # Get all active image filenames from MongoDB
    mongo_filenames = set(all_filenames())

    # Find orphaned vectors
    orphaned = vector_ids - mongo_filenames

    if orphaned:
        collection.delete(ids=list(orphaned))
        print(f"Removed {len(orphaned)} orphaned vectors")

    return len(orphaned)

# ---------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------
if __name__ == "__main__":
    print("🔄 Embedding all un-indexed images …")
    embed_all_from_mongo()
    print("🧹 Cleaning up orphaned vectors …")
    orphaned_count = cleanup_orphaned_vectors()
    print("✅ Done.")
