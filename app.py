"""Inicializador local da API Lumina POS."""

from pathlib import Path
import sys

import uvicorn


BACKEND_DIR = Path(__file__).resolve().parent / "meu_erp_backend"
sys.path.insert(0, str(BACKEND_DIR))


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        # Processo estavel para uso continuo; use uvicorn --reload no desenvolvimento.
        reload=False,
        app_dir=str(BACKEND_DIR),
    )
