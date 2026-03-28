# 🔍 AI-Powered Semantic Image Search Platform

An intelligent image search platform that enables users to search images using **natural language queries** or **image inputs**.
Built using **OpenAI CLIP**, this system understands the semantic meaning of images for accurate and fast retrieval.

---

![Python](https://img.shields.io/badge/python-v3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-v1.0+-red.svg)
![MongoDB](https://img.shields.io/badge/mongodb-v6.0+-green.svg)

---

## 🚀 Features

* 🔍 **Semantic Search** – Search images using natural language (e.g., *"dog playing in park"*)
* 🖼️ **Image-to-Image Search** – Find visually similar images
* 📦 **Image Storage** – Stored efficiently using MongoDB GridFS
* ⚡ **Fast Retrieval** – Vector similarity search using ChromaDB
* 🧠 **CLIP Embeddings** – Semantic understanding of images
* 🗑️ **Trash System** – Delete and restore images
* 🖼️ **Gallery View** – Browse and manage uploaded images

---

## 🏗️ Architecture

```
Streamlit UI  ◄──►  CLIP Model  ◄──►  MongoDB (GridFS)
     │                                 │
     └──────────────► ChromaDB ◄────────┘
```

---

## 🏗️ Tech Stack

* **Frontend**: Streamlit
* **Backend**: Python
* **Database**: MongoDB (GridFS)
* **Vector Database**: ChromaDB
* **ML Model**: OpenCLIP (CLIP-based embeddings)
* **Libraries**: PyTorch, Pillow, NumPy

---

## 📁 Project Structure

```
Text-Image-Search-CLIP/
├── main.py                # Embedding & indexing logic
├── front_end.py          # Streamlit UI
├── utils/                # MongoDB utilities
├── Images_Raw/           # Input images
├── image_vecs_db/        # Vector database
├── requirements.txt
└── README.md
```

---

## ⚙️ Installation

1. Clone the repository:

```
git clone <repo-url>
cd Text-Image-Search-CLIP
```

2. Create a virtual environment:

```
python3.10 -m venv myenv
source myenv/bin/activate
```

3. Install dependencies:

```
pip install -r requirements.txt
```

---

## ▶️ Running the Project

### 1. Run backend (embedding & indexing)

```
python main.py
```

### 2. Run frontend (Streamlit app)

```
streamlit run front_end.py
```

Open in browser:

```
http://localhost:8501
```

---

## 🧪 Usage

1. **Upload Images** – Add images through the interface
2. **Search** – Enter natural language queries
3. **Explore** – View, delete, or restore images

---

## ⚙️ Configuration

* **Database Name**: `image_db`
* **Supported Formats**: PNG, JPG, JPEG

---

## ⚠️ Notes

* Use **Python 3.10 or 3.11** (recommended)
* Ensure MongoDB is running
* First run may take time (embedding process)

---

## 🛠️ Troubleshooting

* **MongoDB not working**

  ```
  mongosh --eval "db.adminCommand('ping')"
  ```

* **Streamlit not opening**

  ```
  streamlit run front_end.py
  ```

* **Memory issues**
  Ensure at least **4GB RAM** available

