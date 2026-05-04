"""Dashboard and history pages."""

import os
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from app.core.config import TEMPLATE_DIR

router = APIRouter()


@router.get("/")
async def dashboard():
    try:
        index_path = os.path.join(TEMPLATE_DIR, "index.html")
        with open(index_path, "r", encoding="utf-8") as file:
            content = file.read()
        return HTMLResponse(content)
    except Exception as exc:
        return JSONResponse({"error": str(exc), "type": type(exc).__name__}, status_code=500)


@router.get("/history")
async def history_page():
    try:
        history_path = os.path.join(TEMPLATE_DIR, "history.html")
        with open(history_path, "r", encoding="utf-8") as file:
            content = file.read()
        return HTMLResponse(content)
    except Exception as exc:
        return JSONResponse({"error": str(exc), "type": type(exc).__name__}, status_code=500)
