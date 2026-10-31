"""内置默认封面文生图提示词与参数。"""
from __future__ import annotations

DEFAULT_IMAGE_COVER_SYSTEM_PROMPT = (
    "You are a product designer creating a notebook cover illustration. "
    "Output must be a clean, modern, high-quality image suitable as a book/notebook cover. "
    "Rules: no text, no letters, no watermarks, no logos, no UI chrome; "
    "strong subject that matches the notebook topic; "
    "balanced composition for a tall portrait cover; "
    "rich but tasteful color; soft lighting; avoid clutter and generic stock-photo look."
)

DEFAULT_IMAGE_COVER_USER_PROMPT = (
    "Notebook title: {title}\n"
    "Description: {description}\n"
    "Create a portrait notebook cover image that visually represents this topic. "
    "Focus on concrete objects/scenes implied by the title and description. "
    "Absolutely no text in the image."
)

DEFAULT_IMAGE_COVER_SIZE = "512x768"
