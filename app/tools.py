"""
Modul Tools: fungsi "aksi" yang dipanggil router ketika intent
BUKAN pertanyaan informasi/kebijakan, melainkan permintaan spesifik
yang butuh pengecekan data langsung (bukan retrieval semantik).

Pola ini mengikuti konsep Tool Integration di Sesi 12.3.
"""

from functools import cache
from pathlib import Path

import pandas as pd

MOCK_TICKETS_PATH = Path(__file__).resolve().parent.parent / "data" / "mock_tickets.csv"


@cache
def _load_tickets() -> pd.DataFrame:
    """Memuat mock_tickets.csv sekali saja. Semua kolom dibaca sebagai string."""
    return pd.read_csv(MOCK_TICKETS_PATH, dtype=str)


def get_ticket_status(ticket_id: str) -> dict:
    """
    Mencari status tiket berdasarkan ticket_id pada data mock_tickets.csv.

    Mengembalikan {"found": bool, "message": str}. Input yang kosong atau
    tidak dikenal tidak melempar error, hanya found=False dengan pesan.
    """
    ticket_id = str(ticket_id or "").strip().upper()
    if not ticket_id:
        return {
            "found": False,
            "message": "Nomor tiket kosong. Tuliskan nomornya, contoh: TICKET-0005.",
        }

    tickets = _load_tickets()
    matches = tickets[tickets["ticket_id"].str.strip().str.upper() == ticket_id]
    if matches.empty:
        return {
            "found": False,
            "message": (
                f"Tiket {ticket_id} tidak ditemukan. "
                "Periksa kembali nomor tiketnya (format TICKET-XXXX)."
            ),
        }

    row = matches.iloc[0]
    return {
        "found": True,
        "message": (
            f"Tiket {row['ticket_id']} ({row['subject']}, kategori {row['category']}) "
            f"atas nama {row['employee_name']} saat ini berstatus {row['status']}. "
            f"Update terakhir: {row['last_update']}."
        ),
    }
