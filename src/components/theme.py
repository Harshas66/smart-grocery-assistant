# src/components/theme.py
from pathlib import Path
import base64
import streamlit as st

ASSETS = Path("assets")  # put your images here (jpg/png)

def _b64_img(path: Path) -> str:
    data = path.read_bytes()
    return base64.b64encode(data).decode("utf-8")

def set_background(image_name: str, darken: float = 0.15):
    """
    image_name: e.g. "dashboard.jpg" placed in assets/
    darken: overlay darkness 0..1
    """
    img_path = ASSETS / image_name
    if not img_path.exists():
        return
    b64 = _b64_img(img_path)
    st.markdown(f"""
        <style>
        .stApp {{
            background:
              linear-gradient(rgba(0,0,0,{darken}), rgba(0,0,0,{darken})),
              url("data:image/jpg;base64,{b64}");
            background-size: cover;
            background-attachment: fixed;
            background-position: center;
        }}
        .st-emotion-cache-1r6slb0, .st-emotion-cache-16idsys {{
            background: rgba(255,255,255,0.85) !important;
            border-radius: 16px !important;
        }}
        </style>
    """, unsafe_allow_html=True)