"""
Router: menentukan apakah query user butuh RAG (informasi/kebijakan)
atau tool call (aksi spesifik, misal cek status tiket).

Pola ini mengikuti workflow router yang sudah dipelajari di Sesi 12.4:
  user input -> intent detection -> jika butuh data -> retrieval (RAG)
                                  -> jika butuh aksi -> tool call
"""

import asyncio
import logging
import re

from app.rag import LLMError, answer_from_knowledge_base, call_llm
from app.tools import get_ticket_status

logger = logging.getLogger(__name__)

# Angka setelah "tiket" yang diikuti satuan waktu ("tiket 3 hari") adalah durasi,
# bukan nomor. Kalau ditulis dengan "-", "#", atau ":" ("TICKET-0005 hari ini")
# tetap dianggap nomor.
TICKET_ID_PATTERN = re.compile(
    r"\b(?:ticket|tiket)[\s\-_#:]*(?:(?:no\.?|nomor)[\s:#]*)?"
    r"((?<=[\-#:])\d+|\d+(?!\s*(?:hari|jam|menit|minggu|bulan|kali)\b))\b",
    re.IGNORECASE,
)

# Frasa yang menandakan user mau cek tiket walau tidak menyebut nomornya
TICKET_KEYWORDS = (
    "status tiket",
    "status ticket",
    "tiket saya",
    "my ticket",
    "cek tiket",
    "progres tiket",
    "progress tiket",
)

INTENT_PROMPT = """Kamu adalah classifier intent untuk chatbot helpdesk internal People & IT.
Klasifikasikan pertanyaan user ke tepat satu label berikut:

- faq: pertanyaan kebijakan, prosedur, atau informasi seputar HR, cuti, absensi, \
akses & password, perangkat kerja, onboarding, payroll, kebijakan kerja, dan tools kolaborasi.
- ticket_status: user ingin mengecek status atau progres tiket helpdesk miliknya.
- unknown: di luar cakupan People & IT (pengetahuan umum, obrolan, atau permintaan lain).

Jawab hanya dengan satu kata: faq, ticket_status, atau unknown.

Pertanyaan: {query}
Label:"""


def extract_ticket_id(query: str) -> str | None:
    """
    Mengekstrak nomor tiket dari teks query dan menormalkannya ke format
    'TICKET-XXXX' seperti di mock_tickets.csv. Mengembalikan None jika tidak ada.
    """
    match = TICKET_ID_PATTERN.search(query)
    if match is None:
        return None
    # int() dulu supaya "ticket 7" dan "TICKET-0007" sama-sama jadi TICKET-0007
    return f"TICKET-{int(match.group(1)):04d}"


def detect_intent_by_keyword(query: str) -> str:
    """Baseline deterministik: ada nomor tiket atau keyword tiket -> ticket_status, selain itu faq."""
    if extract_ticket_id(query) or any(k in query.lower() for k in TICKET_KEYWORDS):
        return "ticket_status"
    return "faq"


def _parse_label(text: str) -> str | None:
    """Mengambil label intent dari jawaban LLM. None jika tidak ada atau lebih dari satu label."""
    labels = set(re.findall(r"ticket_status|unknown|faq", text.lower()))
    # jawaban yang menyebut beberapa label ("faq, bukan unknown") ambigu, serahkan ke keyword
    return labels.pop() if len(labels) == 1 else None


async def detect_intent(query: str) -> str:
    """
    Menentukan intent dari query user. Mengembalikan salah satu:
      - "faq"           -> pertanyaan informasi/kebijakan, arahkan ke RAG
      - "ticket_status"  -> permintaan cek status tiket, arahkan ke tool call
      - "unknown"        -> di luar cakupan helpdesk

    Nomor tiket di query sudah cukup jelas, jadi tidak perlu LLM. Sisanya
    diklasifikasi LLM (structured prompt, Sesi 10.1); kalau LLM gagal atau
    jawabannya tidak dikenali, pakai keyword sebagai cadangan.
    """
    if extract_ticket_id(query) is not None:
        logger.info("intent=ticket_status (regex)")
        return "ticket_status"

    label = None
    try:
        raw = await asyncio.to_thread(
            call_llm, INTENT_PROMPT.format(query=query), temperature=0.0
        )
        label = _parse_label(raw)
    except LLMError:
        logger.warning("LLM gagal untuk intent detection, pakai keyword")

    if label is None:
        label = detect_intent_by_keyword(query)
        logger.info("intent=%s (keyword-fallback)", label)
    else:
        logger.info("intent=%s (llm)", label)
    return label


async def handle_query(query: str) -> dict:
    """
    Fungsi utama yang dipanggil oleh endpoint /ask.
    Menjalankan intent detection, lalu merutekan ke RAG atau tool call yang sesuai.
    """
    intent = await detect_intent(query)

    if intent == "ticket_status":
        ticket_id = extract_ticket_id(query)
        if ticket_id is None:
            return {
                "status": "error",
                "intent": "ticket_status",
                "data": "Nomor tiket belum disebutkan. Tuliskan nomornya, contoh: TICKET-0005.",
            }
        result = get_ticket_status(ticket_id)
        status = "success" if result["found"] else "not_found"
        return {"status": status, "intent": "ticket_status", "data": result["message"]}

    elif intent == "faq":
        data = await answer_from_knowledge_base(query)
        return {"status": "success", "intent": "faq", "data": data}

    else:
        return {
            "status": "error",
            "intent": "unknown",
            "data": (
                "Maaf, permintaan ini di luar cakupan helpdesk People & IT. "
                "Saya bisa membantu pertanyaan kebijakan HR/IT atau cek status tiket "
                "(contoh: TICKET-0005)."
            ),
        }
