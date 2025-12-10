import os
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import shutil

from ai_clone_server.core.config_manager import ConfigManager
from ai_clone_server.core.model_engine import ModelEngine
from ai_clone_server.core.rag_engine import RAGEngine
from ai_clone_server.core.connector_manager import ConnectorManager


# ---------------------------------------------------------------------
# Paths (через Path, не зависят от cwd)
# ---------------------------------------------------------------------
# .../ai-clone-bundle/ai_clone_server/app.py
# BASE_DIR -> .../ai-clone-bundle
BASE_DIR: Path = Path(__file__).resolve().parents[1]

CONFIG_PATH: Path = BASE_DIR / "config" / "config.yaml"
# Prefer new frontend build if exists, otherwise fallback to legacy webui
NEW_FRONTEND_DIST: Path = BASE_DIR / "frontend" / "dist"
WEBUI_PATH: Path = NEW_FRONTEND_DIST if NEW_FRONTEND_DIST.exists() else BASE_DIR / "ai_clone_server" / "webui"
RAG_FILES_DIR: Path = BASE_DIR / "data" / "rag" / "files"
RAG_FILES_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------
# Core components
# ---------------------------------------------------------------------
config_manager = ConfigManager(str(CONFIG_PATH))
rag_engine = RAGEngine(config_manager)
model_engine = ModelEngine(config_manager)
connector_manager = ConnectorManager(config_manager, model_engine, rag_engine)

app = FastAPI(title="AI Clone Server")


# ---------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    print(f"DEBUG BASE_DIR = {BASE_DIR}")
    print(f"DEBUG WEBUI_PATH = {WEBUI_PATH}")
    index_path = WEBUI_PATH / "index.html"
    print(f"DEBUG Index file exists? {index_path.exists()}")
    connector_manager.update_connectors()


@app.on_event("shutdown")
async def shutdown_event():
    if connector_manager.telegram_connector:
        connector_manager.telegram_connector.stop()


# ---------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------
class CloneUpdate(BaseModel):
    system_prompt: str


class TelegramBotConfig(BaseModel):
    bot_id: str
    token: str
    linked_clone_id: str


class TelegramConfigUpdate(BaseModel):
    enabled: bool
    bots: List[TelegramBotConfig]


class ChatRequest(BaseModel):
    message: str
    history: list = []


# ---------------------------------------------------------------------
# Healthcheck
# ---------------------------------------------------------------------
@app.get("/ping")
async def ping():
    return {"status": "ok"}


# ---------------------------------------------------------------------
# Clone config
# ---------------------------------------------------------------------
@app.get("/api/clone")
async def get_clone_config():
    clone_config = config_manager.get("clone")
    return clone_config


@app.put("/api/clone")
async def update_clone_config(update: CloneUpdate):
    config_manager.update_system_prompt(update.system_prompt)
    return {"status": "success", "message": "System prompt updated"}


# ---------------------------------------------------------------------
# Telegram config
# ---------------------------------------------------------------------
@app.get("/api/messengers/telegram")
async def get_telegram_config():
    return config_manager.get("messengers.telegram")


@app.put("/api/messengers/telegram")
async def update_telegram_config(update: TelegramConfigUpdate):
    bots_data = [bot.dict() for bot in update.bots]
    config_manager.set("messengers.telegram.enabled", update.enabled)
    config_manager.set("messengers.telegram.bots", bots_data)

    connector_manager.update_connectors()

    return {"status": "success", "message": "Telegram config updated"}


# ---------------------------------------------------------------------
# RAG
# ---------------------------------------------------------------------
@app.get("/api/rag/documents")
async def get_rag_documents():
    return rag_engine.get_all_documents()


@app.post("/api/rag/documents")
async def upload_rag_document(file: UploadFile = File(...)):
    file_path: Path = RAG_FILES_DIR / file.filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Для MVP читаем как текст
    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        rag_engine.add_document(content, metadata={"filename": file.filename})
    except Exception as e:
        return {"status": "error", "message": str(e)}

    return {
        "status": "success",
        "message": f"File {file.filename} uploaded and indexed",
    }

@app.delete("/api/rag/documents/{doc_id}")
async def delete_rag_document(doc_id: str):
    ok = rag_engine.delete_document(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found or cannot be deleted")
    return {"status": "success", "message": f"Document {doc_id} deleted"}


# ---------------------------------------------------------------------
# Test chat
# ---------------------------------------------------------------------
@app.post("/api/chat/test")
async def chat_test(request: ChatRequest):
    context = ""
    if config_manager.get("rag.enabled"):
        results = rag_engine.search(request.message, top_k=3)
        if results:
            context = "\n\nContext:\n" + "\n".join(results)

    full_message = request.message
    if context:
        full_message += context

    answer = model_engine.generate(full_message, history=request.history)
    return {"answer": answer}


# ---------------------------------------------------------------------
# Web UI (index + статика)
# ---------------------------------------------------------------------

# Отдаём index.html по корню
@app.get("/", response_class=HTMLResponse)
async def read_index():
    index_path = WEBUI_PATH / "index.html"
    if not index_path.exists():
        return HTMLResponse(
            content=f"<h1>Error</h1><p>index.html not found at {index_path}</p>",
            status_code=500,
        )
    # FileResponse чтобы корректно выставлялись заголовки
    return FileResponse(index_path)


# Ассеты (CSS/JS) по /assets/...
app.mount(
    "/assets",
    StaticFiles(directory=str(WEBUI_PATH / "assets")),
    name="assets",
)


# SPA fallback for frontend routes (e.g., /settings, /rag)
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def spa_fallback(full_path: str):
    # Do not intercept API/static
    if full_path.startswith(("api", "assets", "docs", "openapi.json", "favicon.ico")):
        raise HTTPException(status_code=404)
    index_path = WEBUI_PATH / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found")
