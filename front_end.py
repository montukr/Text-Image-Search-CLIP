import streamlit as st, io, base64
from PIL import Image
import chromadb
from chromadb.utils.embedding_functions import OpenCLIPEmbeddingFunction

from utils.mongo_utils import (
    save_image, load_image, load_thumb, all_filenames
)
from main import embed_image

# ---------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------
st.set_page_config(page_title="AI Image Search", layout="wide")
st.title("🔍 AI-Powered Image Search")

# ---------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------
def image_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    fmt = img.format if img.format else "PNG"
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()

def render_frame(fid: str, thumb_img: Image.Image) -> str:
    """Return HTML of uniform 220-px card with gap & click-to-full."""
    b64_thumb = image_to_b64(thumb_img)
    full_img  = load_image(fid)
    b64_full  = image_to_b64(full_img) if full_img else b64_thumb
    return f"""
    <div style='height:220px;margin:6px;overflow:hidden;border-radius:8px;'>
        <a href='data:image/png;base64,{b64_full}' target='_blank'>
            <img src='data:image/png;base64,{b64_thumb}'
                 style='width:100%;height:100%;object-fit:cover;display:block;border-radius:8px;' />
        </a>
    </div>
    """

# ---------------------------------------------------------------
# Chroma client
# ---------------------------------------------------------------
client = chromadb.PersistentClient(path="./image_vecs_db")
collection = client.get_or_create_collection(
    name="image_vecs",
    embedding_function=OpenCLIPEmbeddingFunction()
)

# ---------------------------------------------------------------
# Sidebar – actions
# ---------------------------------------------------------------
st.sidebar.header("Actions")

# ---> Go-to-Search button
if st.sidebar.button("🔎 Go to Search"):
    st.markdown("<meta http-equiv='refresh' content='0; URL=#search-section'>",
                unsafe_allow_html=True)

# ---> Multiple-file upload
files = st.sidebar.file_uploader("Upload images",
                                 type=["png", "jpg", "jpeg"],
                                 accept_multiple_files=True)

if files:
    for file in files:
        save_image(file, file.name)                # original + thumb
        file.seek(0)
        pil = Image.open(io.BytesIO(file.read())).convert("RGB")
        embed_image(file.name, pil)
    st.sidebar.success(f"{len(files)} image(s) uploaded & indexed ✅")

# ---> Bulk embed / refresh
if st.sidebar.button("🔄 Embed / Refresh ALL Vectors"):
    names = list(all_filenames())
    if not names:
        st.sidebar.info("Database is empty.")
    else:
        bar = st.sidebar.progress(0, text="Embedding …")
        for i, fid in enumerate(names, start=1):
            img = load_image(fid)
            if img is not None:
                embed_image(fid, img)
            bar.progress(i / len(names), text=f"{i}/{len(names)} embedded")
        st.sidebar.success("Vector store updated ✔️")

# ---> View all images (with loading bar)
# ---> View all images (progress bar shown in sidebar)
if st.sidebar.button("🖼️ View All Images"):
    show_gallery = True
else:
    show_gallery = False

if show_gallery:
    st.subheader("All images in database")
    names = list(all_filenames())

    if not names:
        st.info("Database is empty.")
    else:
        total = len(names)
        sidebar_bar = st.sidebar.progress(0, text="Loading thumbnails …")
        cols = st.columns(5)

        for idx, fid in enumerate(names, start=1):
            thumb = load_thumb(fid)
            if thumb is not None:
                cols[(idx - 1) % 5].markdown(render_frame(fid, thumb), unsafe_allow_html=True)
            sidebar_bar.progress(idx / total, text=f"{idx}/{total} loaded")

        st.sidebar.success(f"{total} image(s) loaded ✔️")


# ---------------------------------------------------------------
# Search section
# ---------------------------------------------------------------
st.markdown("<a name='search-section'></a>", unsafe_allow_html=True)
st.header("Search")
query = st.text_input("Type a text query:")

if query:
    res = collection.query(query_texts=[query], n_results=10)
    hits = res["ids"][0]
    if hits:
        cols = st.columns(5)
        for idx, fid in enumerate(hits, start=1):
            thumb = load_thumb(fid)
            if thumb is not None:
                cols[(idx - 1) % 5].markdown(render_frame(fid, thumb),
                                              unsafe_allow_html=True)
    else:
        st.info("No matches found.")

st.write("---")
st.caption(
    "Images stored in MongoDB (original + thumbnail) · Vectors in ChromaDB · "
    "Click a frame to view the full-size image in a new tab."
)
