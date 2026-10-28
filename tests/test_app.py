"""
Unit test offline (tanpa jaringan dan tanpa API key). Semua pemanggilan
Gemini diganti dengan monkeypatch.

Jalankan: python -m pytest -q
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app import main, rag, router
from app.tools import get_ticket_status

NO_ID_MESSAGE = "Nomor tiket belum disebutkan. Tuliskan nomornya, contoh: TICKET-0005."


def run(coro):
    return asyncio.run(coro)


def fake_llm(output):
    """Pengganti call_llm: mengembalikan output, atau melempar kalau output berupa exception."""
    calls = []

    def _call(prompt, temperature=0.2):
        calls.append(prompt)
        if isinstance(output, Exception):
            raise output
        return output

    _call.calls = calls
    return _call


# --- extract_ticket_id ---


@pytest.mark.parametrize(
    "query, expected",
    [
        ("TICKET-0042", "TICKET-0042"),
        ("ticket 7", "TICKET-0007"),
        ("status ticket 7 dong", "TICKET-0007"),
        ("Tolong cek tiket no. 5", "TICKET-0005"),
        ("tiket nomor 12", "TICKET-0012"),
        ("tiket #3", "TICKET-0003"),
        ("tiket-12345", "TICKET-12345"),
        ("Cek TICKET-0005 saya", "TICKET-0005"),
        ("tiket nomor: 5", "TICKET-0005"),
        ("tiket no:5", "TICKET-0005"),
        ("Status TICKET-0005 hari ini apa?", "TICKET-0005"),
    ],
)
def test_extract_ticket_id_normalisasi(query, expected):
    assert router.extract_ticket_id(query) == expected


@pytest.mark.parametrize(
    "query",
    [
        "Berapa jatah cuti saya?",
        "tiket saya belum selesai",
        "ticket",
        "",
        "nomor 5",
        # angka setelah "tiket" di sini durasi, bukan nomor tiket
        "Berapa lama tiket 3 hari diproses?",
        "Kalau tiket 2 hari belum diproses bagaimana?",
        "Berapa lama SLA tiket 1 hari kerja?",
        "Apakah tiket 24 jam bisa diprioritaskan?",
        "tiket 1 kali sehari cukup?",
    ],
)
def test_extract_ticket_id_none(query):
    assert router.extract_ticket_id(query) is None


# --- get_ticket_status ---


def test_get_ticket_status_found():
    result = get_ticket_status("TICKET-0005")
    assert result["found"] is True
    assert "TICKET-0005" in result["message"]
    assert "Dedi Kurniawan" in result["message"]
    assert "berstatus Diproses" in result["message"]
    assert "2026-08-27" in result["message"]


@pytest.mark.parametrize(
    "ticket_id", ["ticket-0005", "  TICKET-0005  ", "Ticket-0005\n"]
)
def test_get_ticket_status_input_berantakan(ticket_id):
    assert get_ticket_status(ticket_id)["found"] is True


def test_get_ticket_status_not_found():
    assert get_ticket_status("TICKET-0042") == {
        "found": False,
        "message": (
            "Tiket TICKET-0042 tidak ditemukan. "
            "Periksa kembali nomor tiketnya (format TICKET-XXXX)."
        ),
    }


@pytest.mark.parametrize("ticket_id", ["", "   ", None])
def test_get_ticket_status_kosong_tidak_error(ticket_id):
    result = get_ticket_status(ticket_id)
    assert result["found"] is False
    assert result["message"]


# --- detect_intent ---


def test_detect_intent_regex_tidak_memanggil_llm(monkeypatch):
    llm = fake_llm("faq")
    monkeypatch.setattr(router, "call_llm", llm)
    assert run(router.detect_intent("cek TICKET-0005")) == "ticket_status"
    assert llm.calls == []


@pytest.mark.parametrize(
    "llm_output, expected",
    [
        ("Ticket_Status.", "ticket_status"),
        ("`faq`", "faq"),
        ('"unknown"', "unknown"),
        ("  FAQ\n", "faq"),
        ("Label: ticket_status", "ticket_status"),
    ],
)
def test_detect_intent_parse_label_llm(monkeypatch, llm_output, expected):
    monkeypatch.setattr(router, "call_llm", fake_llm(llm_output))
    # query sengaja tanpa keyword tiket, jadi hasilnya pasti dari LLM
    assert run(router.detect_intent("pertanyaan bebas")) == expected


@pytest.mark.parametrize(
    "query, expected",
    [
        ("Tiket saya kok belum selesai ya?", "ticket_status"),
        ("Berapa jatah cuti tahunan?", "faq"),
    ],
)
def test_detect_intent_output_sampah_pakai_keyword(monkeypatch, query, expected):
    monkeypatch.setattr(router, "call_llm", fake_llm("hmm tidak yakin"))
    assert run(router.detect_intent(query)) == expected


def test_detect_intent_label_ganda_pakai_keyword(monkeypatch):
    # LLM menyebut dua label, jadi hasilnya ambigu dan keyword yang menentukan
    monkeypatch.setattr(router, "call_llm", fake_llm("faq (bukan unknown)"))
    assert run(router.detect_intent("Tiket saya kok belum selesai ya?")) == "ticket_status"


@pytest.mark.parametrize(
    "query, expected",
    [
        ("Tiket saya kok belum selesai ya?", "ticket_status"),
        ("Gimana cara reset password VPN?", "faq"),
    ],
)
def test_detect_intent_llm_error_pakai_keyword(monkeypatch, query, expected):
    monkeypatch.setattr(router, "call_llm", fake_llm(rag.LLMError("semua model gagal")))
    assert run(router.detect_intent(query)) == expected


def test_detect_intent_by_keyword():
    assert router.detect_intent_by_keyword("Cek Tiket saya") == "ticket_status"
    assert router.detect_intent_by_keyword("ticket 7") == "ticket_status"
    assert router.detect_intent_by_keyword("resep nasi goreng") == "faq"


# --- handle_query ---


def test_handle_query_ticket_found(monkeypatch):
    monkeypatch.setattr(router, "call_llm", fake_llm("ticket_status"))
    result = run(router.handle_query("Tolong cek status tiket TICKET-0005 saya"))
    assert result["status"] == "success"
    assert result["intent"] == "ticket_status"
    assert "Dedi Kurniawan" in result["data"]


def test_handle_query_ticket_not_found():
    result = run(router.handle_query("Apa status tiket TICKET-0042 saya?"))
    assert result["status"] == "not_found"
    assert result["intent"] == "ticket_status"
    assert "TICKET-0042 tidak ditemukan" in result["data"]


def test_handle_query_ticket_tanpa_nomor(monkeypatch):
    monkeypatch.setattr(router, "call_llm", fake_llm("ticket_status"))
    result = run(router.handle_query("Tiket saya kok belum selesai ya?"))
    assert result == {
        "status": "error",
        "intent": "ticket_status",
        "data": NO_ID_MESSAGE,
    }


def test_handle_query_faq(monkeypatch):
    async def fake_answer(query):
        return f"jawaban untuk {query}"

    monkeypatch.setattr(router, "call_llm", fake_llm("faq"))
    monkeypatch.setattr(router, "answer_from_knowledge_base", fake_answer)
    result = run(router.handle_query("Berapa jatah cuti?"))
    assert result == {
        "status": "success",
        "intent": "faq",
        "data": "jawaban untuk Berapa jatah cuti?",
    }


def test_handle_query_unknown(monkeypatch):
    monkeypatch.setattr(router, "call_llm", fake_llm("unknown"))
    result = run(router.handle_query("Siapa pemenang Piala Dunia 2022?"))
    assert result["status"] == "error"
    assert result["intent"] == "unknown"
    assert "di luar cakupan" in result["data"]


def test_handle_query_faq_llm_error_naik(monkeypatch):
    async def fake_answer(query):
        raise rag.LLMError("gagal")

    monkeypatch.setattr(router, "call_llm", fake_llm("faq"))
    monkeypatch.setattr(router, "answer_from_knowledge_base", fake_answer)
    with pytest.raises(rag.LLMError):
        run(router.handle_query("Berapa jatah cuti?"))


# --- answer_from_knowledge_base ---


def hasil_search(score):
    return [
        {"faq_id": 1, "category": "Cuti", "question": "Q?", "answer": "A.", "score": score}
    ]


def test_rag_skor_rendah_tidak_memanggil_llm(monkeypatch):
    llm = fake_llm("seharusnya tidak dipanggil")
    monkeypatch.setattr(
        rag, "semantic_search", lambda q: hasil_search(rag.MIN_SCORE - 0.01)
    )
    monkeypatch.setattr(rag, "call_llm", llm)
    assert run(rag.answer_from_knowledge_base("resep nasi goreng")) == rag.NO_ANSWER
    assert llm.calls == []


def test_rag_tanpa_hasil_tidak_memanggil_llm(monkeypatch):
    llm = fake_llm("x")
    monkeypatch.setattr(rag, "semantic_search", lambda q: [])
    monkeypatch.setattr(rag, "call_llm", llm)
    assert run(rag.answer_from_knowledge_base("apa saja")) == rag.NO_ANSWER
    assert llm.calls == []


def test_rag_skor_cukup_memanggil_llm_dengan_context(monkeypatch):
    llm = fake_llm("12 hari per tahun.")
    monkeypatch.setattr(
        rag, "semantic_search", lambda q: hasil_search(rag.MIN_SCORE + 0.05)
    )
    monkeypatch.setattr(rag, "call_llm", llm)
    assert run(rag.answer_from_knowledge_base("jatah cuti?")) == "12 hari per tahun."
    for bagian in ("Persona:", "Task:", "Context:", "Format:", "[FAQ 1]"):
        assert bagian in llm.calls[0]


# --- endpoint /ask ---


@pytest.fixture
def client(monkeypatch):
    # lifespan memanggil build_index, diganti supaya tidak ke Gemini
    monkeypatch.setattr(rag, "build_index", lambda: None)
    with TestClient(main.app) as c:
        yield c


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert isinstance(body["index_ready"], bool)


def test_ask_200_envelope(client, monkeypatch):
    async def fake_handle(query):
        return {"status": "success", "intent": "faq", "data": f"ok {query}"}

    monkeypatch.setattr(main, "handle_query", fake_handle)
    response = client.post("/ask", json={"query": "  halo  "})
    assert response.status_code == 200
    # spasi di pinggir sudah dibuang validator
    assert response.json() == {"status": "success", "intent": "faq", "data": "ok halo"}


@pytest.mark.parametrize(
    "payload", [{"query": ""}, {"query": "   "}, {}, {"query": "x" * 501}]
)
def test_ask_query_tidak_valid_422(client, payload):
    assert client.post("/ask", json=payload).status_code == 422


def test_ask_llm_error_503(client, monkeypatch):
    async def fake_handle(query):
        raise rag.LLMError("gagal")

    monkeypatch.setattr(main, "handle_query", fake_handle)
    response = client.post("/ask", json={"query": "halo"})
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert "tidak dapat dihubungi" in body["data"]


def test_ask_error_tak_terduga_500_tanpa_bocor(client, monkeypatch):
    async def fake_handle(query):
        raise ValueError("rahasia-internal-123")

    monkeypatch.setattr(main, "handle_query", fake_handle)
    response = client.post("/ask", json={"query": "halo"})
    assert response.status_code == 500
    assert response.json()["status"] == "error"
    assert "rahasia-internal-123" not in response.text
