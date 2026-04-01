import streamlit as st, io, base64
from PIL import Image

from utils.mongo_utils import (
    save_image, load_image, load_thumb, all_filenames,
    move_to_trash, restore_from_trash, permanently_delete,
    all_trash_filenames, load_deleted_thumb, load_deleted_image
)
from main import embed_image, remove_image_vector, embed_all_from_mongo, query_images

# ---------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------
st.set_page_config(page_title="AI Image Search", layout="wide")
st.title("🔍 AI-Powered Image Search")

# ---------------------------------------------------------------
# Global JavaScript Injection
# ---------------------------------------------------------------
st.markdown("""
<script>
    function toggleMenu(menuId) {
        var menu = document.getElementById(menuId);
        var isVisible = menu.style.display === 'block';

        // Hide all menus first
        var allMenus = document.querySelectorAll('[id^="menu-"], [id^="trash-menu-"]');
        allMenus.forEach(function(m) { m.style.display = 'none'; });

        // Show current menu if it wasn't visible
        if (!isVisible) {
            menu.style.display = 'block';
        }
    }

    // Hide menus when clicking outside
    document.addEventListener('click', function(event) {
        if (!event.target.closest('[id^="menu-"]') && !event.target.closest('[id^="trash-menu-"]') && !event.target.matches('button')) {
            var allMenus = document.querySelectorAll('[id^="menu-"], [id^="trash-menu-"]');
            allMenus.forEach(function(m) { m.style.display = 'none'; });
        }
    });
</script>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------
# Initialize session state for UI control
# ---------------------------------------------------------------
if 'current_view' not in st.session_state:
    st.session_state.current_view = 'search'
if 'delete_confirm' not in st.session_state:
    st.session_state.delete_confirm = {}
if 'uploaded_files_hash' not in st.session_state:
    st.session_state.uploaded_files_hash = None
if 'upload_complete' not in st.session_state:
    st.session_state.upload_complete = False

# ---------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------
def image_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    fmt = img.format if img.format else "PNG"
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()

@st.cache_data(show_spinner=False)
def _get_b64(fid: str, is_trash: bool, is_full: bool) -> str:
    """Fetches image from DB and converts to Base64, heavily cached for speed."""
    if is_trash:
        img = load_deleted_image(fid) if is_full and 'load_deleted_image' in globals() else load_deleted_thumb(fid)
    else:
        img = load_image(fid) if is_full else load_thumb(fid)
    return image_to_b64(img) if img else ""

def render_frame_with_menu(fid: str, is_trash: bool = False) -> str:
    """Return HTML of uniform 220-px card with three-dot menu for delete options."""
    b64_thumb = _get_b64(fid, is_trash, False)
    if not b64_thumb:
        return ""
        
    b64_full = _get_b64(fid, is_trash, True) or b64_thumb
    menu_id = f"trash-menu-{fid.replace('.', '_').replace(' ', '_')}" if is_trash else f"menu-{fid.replace('.', '_').replace(' ', '_')}"

    return f"""
    <div style='position:relative;height:220px;margin:6px;overflow:hidden;border-radius:8px;'>
        <a href='data:image/png;base64,{b64_full}' target='_blank'>
            <img src='data:image/png;base64,{b64_thumb}'
                 style='width:100%;height:100%;object-fit:cover;display:block;border-radius:8px;' />
        </a>

        <!-- Three-dot menu button -->
        <div style='position:absolute;top:5px;right:5px;'>
            <button onclick='toggleMenu("{menu_id}")'
                    style='background:rgba(0,0,0,0.7);border:none;color:white;padding:5px 8px;border-radius:50%;cursor:pointer;font-size:16px;'>
                ⋮
            </button>
        </div>

        <!-- Dropdown menu -->
        <div id='{menu_id}' style='position:absolute;top:35px;right:5px;background:white;border:1px solid #ccc;border-radius:4px;box-shadow:0 2px 8px rgba(0,0,0,0.1);display:none;min-width:120px;z-index:1000;'>
            {_get_menu_content(fid, is_trash)}
        </div>
    </div>
    """

def _get_menu_content(fid: str, is_trash: bool) -> str:
    """Generate menu content based on whether item is in trash or not."""
    fid_key = fid.replace('.', '_').replace(' ', '_')

    if is_trash:
        return f"""
            <div style='padding:5px 0;'>
                <button onclick='window.parent.postMessage({{action:"restore", filename:"{fid}"}}, "*")'
                        style='width:100%;padding:8px 12px;border:none;background:none;text-align:left;cursor:pointer;color:#28a745;'>
                    🔄 Restore
                </button>
                <button onclick='window.parent.postMessage({{action:"permanent_delete", filename:"{fid}"}}, "*")'
                        style='width:100%;padding:8px 12px;border:none;background:none;text-align:left;cursor:pointer;color:#dc3545;'>
                    🗑️ Delete Forever
                </button>
            </div>
        """
    else:
        return f"""
            <div style='padding:5px 0;'>
                <button onclick='window.parent.postMessage({{action:"delete", filename:"{fid}"}}, "*")'
                        style='width:100%;padding:8px 12px;border:none;background:none;text-align:left;cursor:pointer;color:#dc3545;'>
                    🗑️ Delete
                </button>
            </div>
        """

def handle_menu_actions():
    """Handle menu actions from JavaScript messages."""
    pass

# ---------------------------------------------------------------
# Core UI Components
# ---------------------------------------------------------------

def render_sidebar():
    st.sidebar.header("Actions")

    # ---> Go-to-Search button
    if st.sidebar.button("🔎 Search Images"):
        st.session_state.current_view = 'search'

    # ---> Multiple-file upload with progress bar
    files = st.sidebar.file_uploader("Upload images",
                                     type=["png", "jpg", "jpeg"],
                                     accept_multiple_files=True)

    if files:
        # Create a hash of the uploaded files to detect changes
        files_info = [(f.name, f.size) for f in files]
        current_files_hash = hash(str(files_info))

        # Only process if files have changed or haven't been processed yet
        if (st.session_state.uploaded_files_hash != current_files_hash or
            not st.session_state.upload_complete):

            st.session_state.uploaded_files_hash = current_files_hash
            st.session_state.upload_complete = False

            total_files = len(files)
            upload_bar = st.sidebar.progress(0, text="Uploading images …")

            success_count = 0
            failed_files = []

            for i, file in enumerate(files, start=1):
                try:
                    upload_bar.progress(
                        (i - 1) / total_files,
                        text=f"Uploading {file.name} ({i}/{total_files}) …"
                    )

                    save_image(file, file.name)

                    file.seek(0)
                    pil = Image.open(io.BytesIO(file.read())).convert("RGB")
                    embed_image(file.name, pil)

                    success_count += 1

                    upload_bar.progress(
                        i / total_files,
                        text=f"Uploaded {file.name} ({i}/{total_files})"
                    )
                except Exception as e:
                    failed_files.append((file.name, str(e)))
                    upload_bar.progress(
                        i / total_files,
                        text=f"Failed: {file.name} ({i}/{total_files})"
                    )

            upload_bar.progress(1.0, text=f"Upload complete!")
            st.session_state.upload_complete = True

            if success_count > 0:
                st.sidebar.success(f"✅ {success_count} image(s) uploaded & indexed successfully")

            if failed_files:
                st.sidebar.error(f"❌ {len(failed_files)} file(s) failed to upload:")
                for filename, error in failed_files:
                    st.sidebar.error(f"• {filename}: {error}")
        else:
            st.sidebar.info(f"📁 {len(files)} file(s) selected (already processed)")
            if st.sidebar.button("🔄 Re-upload Selected Files", help="Force re-upload of selected files"):
                st.session_state.upload_complete = False
                st.rerun()

    # ---> Bulk embed / refresh using refactored main.py function
    if st.sidebar.button("🔄 Embed / Refresh ALL Vectors"):
        names = list(all_filenames())
        if not names:
            st.sidebar.info("Database is empty.")
        else:
            bar = st.sidebar.progress(0, text="Embedding …")
            def progress_callback(idx, total, fid):
                bar.progress(idx / total, text=f"{idx}/{total} embedded ({fid})")
            
            embed_all_from_mongo(progress_callback=progress_callback)
            st.sidebar.success("Vector store updated ✔️")

    # ---> View all images button
    if st.sidebar.button("🖼️ View All Images"):
        st.session_state.current_view = 'gallery'

    # ---> Trash button
    if st.sidebar.button("🗑️ Trash"):
        st.session_state.current_view = 'trash'


def render_gallery():
    st.subheader("All images in database")
    names = list(all_filenames())

    if not names:
        st.info("Database is empty.")
    else:
        total = len(names)
        sidebar_bar = st.sidebar.progress(0, text="Loading thumbnails …")

        cols = st.columns(5)
        for idx, fid in enumerate(names, start=1):
            col_idx = (idx - 1) % 5

            delete_key = f"delete_{fid}"
            if st.session_state.get(delete_key, False):
                if move_to_trash(fid):
                    remove_image_vector(fid)
                    st.success(f"Moved {fid} to trash")
                    st.session_state[delete_key] = False
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Failed to delete {fid}")

            html = render_frame_with_menu(fid, is_trash=False)
            if html:
                with cols[col_idx]:
                    st.markdown(html, unsafe_allow_html=True)
                    if st.button(f"🗑️", key=f"del_{fid}", help="Delete image"):
                        st.session_state[delete_key] = True
                        st.rerun()
            
            sidebar_bar.progress(idx / total, text=f"{idx}/{total} loaded")
            
        st.sidebar.success(f"{total} image(s) loaded ✔️")


def render_trash():
    st.subheader("🗑️ Trash")
    trash_names = list(all_trash_filenames())

    if not trash_names:
        st.info("Trash is empty.")
    else:
        st.write(f"**{len(trash_names)} item(s) in trash**")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Restore All"):
                restored_count = 0
                for fid in trash_names:
                    if restore_from_trash(fid):
                        img = load_image(fid)
                        if img:
                            embed_image(fid, img)
                        restored_count += 1
                st.success(f"Restored {restored_count} image(s)")
                st.cache_data.clear()
                st.rerun()

        with col2:
            if st.button("🗑️ Empty Trash", type="secondary"):
                if st.session_state.get('confirm_empty_trash', False):
                    deleted_count = 0
                    for fid in trash_names:
                        if permanently_delete(fid):
                            deleted_count += 1
                    st.success(f"Permanently deleted {deleted_count} image(s)")
                    st.session_state['confirm_empty_trash'] = False
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.session_state['confirm_empty_trash'] = True
                    st.warning("Click again to confirm permanent deletion of all items")

        cols = st.columns(5)
        for idx, fid in enumerate(trash_names, start=1):
            col_idx = (idx - 1) % 5

            restore_key = f"restore_{fid}"
            if st.session_state.get(restore_key, False):
                if restore_from_trash(fid):
                    img = load_image(fid)
                    if img:
                        embed_image(fid, img)
                    st.success(f"Restored {fid}")
                    st.session_state[restore_key] = False
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Failed to restore {fid}")

            perm_delete_key = f"perm_delete_{fid}"
            if st.session_state.get(perm_delete_key, False):
                if permanently_delete(fid):
                    st.success(f"Permanently deleted {fid}")
                    st.session_state[perm_delete_key] = False
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Failed to permanently delete {fid}")

            b64_thumb = _get_b64(fid, is_trash=True, is_full=False)
            if b64_thumb:
                with cols[col_idx]:
                    st.markdown(f"<img src='data:image/png;base64,{b64_thumb}' style='width:100%;border-radius:8px;'/>", unsafe_allow_html=True)
                    st.caption(fid)
                    button_col1, button_col2 = st.columns(2)
                    with button_col1:
                        if st.button("🔄", key=f"restore_btn_{fid}", help="Restore"):
                            st.session_state[restore_key] = True
                            st.rerun()
                    with button_col2:
                        if st.button("🗑️", key=f"perm_del_btn_{fid}", help="Delete Forever"):
                            st.session_state[perm_delete_key] = True
                            st.rerun()


def render_search():
    st.markdown("<a name='search-section'></a>", unsafe_allow_html=True)
    st.header("Search")
    query = st.text_input("Type a text query:")

    if query:
        hits = query_images(query, n_results=10)
        if hits:
            cols = st.columns(5)
            for idx, fid in enumerate(hits, start=1):
                col_idx = (idx - 1) % 5

                search_delete_key = f"search_delete_{fid}"
                if st.session_state.get(search_delete_key, False):
                    if move_to_trash(fid):
                        remove_image_vector(fid)
                        st.success(f"Moved {fid} to trash")
                        st.session_state[search_delete_key] = False
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Failed to delete {fid}")

                html = render_frame_with_menu(fid, is_trash=False)
                if html:
                    with cols[col_idx]:
                        st.markdown(html, unsafe_allow_html=True)
                        if st.button(f"🗑️", key=f"search_del_{fid}", help="Delete image"):
                            st.session_state[search_delete_key] = True
                            st.rerun()
        else:
            st.info("No matches found.")


# ---------------------------------------------------------------
# Main Layout Execution
# ---------------------------------------------------------------
def main():
    render_sidebar()

    if st.session_state.current_view == 'gallery':
        render_gallery()
    elif st.session_state.current_view == 'trash':
        render_trash()
    else:
        render_search()
    
    st.write("---")
    st.caption(
        "Images stored in MongoDB (original + thumbnail) · Vectors in ChromaDB · "
        "Click a frame to view the full-size image in a new tab. · "
        "Use delete buttons to manage images."
    )

if __name__ == "__main__":
    main()
