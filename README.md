# 🔍 AI-Powered Semantic Image Search Platform

Search images using natural language with OpenAI's CLIP model. Upload images and find them with queries like "dog playing in park" or "sunset over mountains".

![Python](https://img.shields.io/badge/python-v3.8+-blue.svg) ![Streamlit](https://img.shields.io/badge/streamlit-v1.28+-red.svg) ![MongoDB](https://img.shields.io/badge/mongodb-v6.0+-green.svg)

## Features

- **Semantic Search**: Find images with natural language
- **Batch Upload**: Multiple image uploads with progress tracking
- **Smart Thumbnails**: Auto-generated thumbnails and caching
- **Gallery View**: Browse and manage all images
- **Trash System**: Delete and restore images


## Usage

1. **Upload**: Drop images in the sidebar uploader
2. **Search**: Type natural language queries 
3. **Manage**: View gallery, delete, or restore images

## Architecture

```
Streamlit ◄──► OpenAI CLIP ◄──► MongoDB + GridFS
    │              │                    │
    └──────────► ChromaDB ◄─────────────┘
```

## Configuration

- **Database**: `image_db`
- **Supported Formats**: PNG, JPG, JPEG


## Troubleshooting

**MongoDB Issues**: Check if MongoDB is running with `mongosh --eval "db.adminCommand('ping')"`

**Memory Issues**: Ensure 4GB+ RAM available

## Contact

- **LinkedIn: https://www.linkedin.com/in/montukr/
