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

def embed_all_from_mongo() -> None:
    """Index anything in MongoDB that isn't in Chroma yet."""
    for fid in all_filenames():
        if not collection.peek(ids=[fid])["metadatas"]:
            img = load_image(fid)
            if img is not None:
                embed_image(fid, img)

# ---------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------
if __name__ == "__main__":
    print("🔄 Embedding all un-indexed images …")
    embed_all_from_mongo()
    print("✅ Done.")
