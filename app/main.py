"""
Entry point aplikasi FastAPI untuk IT Helpdesk Assistant.

Alur endpoint utama:
  1. Menerima pertanyaan/permintaan dari user
  2. Meneruskan ke router (router.py) untuk menentukan intent
  3. Router memanggil RAG (rag.py) atau tool (tools.py) sesuai intent
  4. Mengembalikan response terstruktur ke client
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app import rag
from app.rag import LLMError
from app.router import handle_query

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bangun index FAISS sekali saat startup, bukan di setiap request."""
    try:
        await asyncio.to_thread(rag.build_index)
    except Exception:
        # tanpa index (atau API key) service tidak berguna, jadi langsung gagal
        logger.exception("Gagal membangun index saat startup")
        raise
    yield


app = FastAPI(title="IT Helpdesk Assistant API", lifespan=lifespan)


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query tidak boleh kosong")
        return value


class AskResponse(BaseModel):
    status: str
    intent: str
    data: str


@app.get("/health")
async def health():
    """Endpoint sederhana untuk memastikan service berjalan."""
    return {"status": "ok", "index_ready": rag.is_ready()}


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    """
    Endpoint utama. Menerima pertanyaan bebas dari user (bisa berupa
    pertanyaan informasi/kebijakan ATAU permintaan cek status tiket),
    lalu meneruskannya ke router untuk diproses.

    Jika Gemini tidak bisa dihubungi dikembalikan 503, untuk error lain 500
    dengan pesan umum (detail error hanya masuk log).
    """
    try:
        result = await handle_query(request.query)
    except LLMError:
        logger.exception("Gemini tidak dapat dihubungi")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "intent": "faq",
                "data": "Layanan LLM sedang tidak dapat dihubungi. Silakan coba lagi beberapa saat.",
            },
        )
    except Exception:
        logger.exception("Error tak terduga saat memproses /ask")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "intent": "unknown",
                "data": "Terjadi kesalahan pada server. Silakan coba lagi.",
            },
        )
    return AskResponse(**result)
