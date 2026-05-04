"""Run Script - Entry Point (FastAPI + Uvicorn)."""

import os
import sys
import io

from app.core.config import HOST, PORT, RELOAD, LOG_LEVEL

# Fix encoding cho Windows terminal
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 80)
    print("🗑️  Trash Classification System - FastAPI + Multiprocessing")
    print("=" * 80 + "\n")

    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=RELOAD,
        log_level=LOG_LEVEL,
        workers=1,
    )
