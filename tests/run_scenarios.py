"""
Menjalankan skenario uji end-to-end ke endpoint /ask, lalu menulis hasilnya ke
documentation/test_results.md dan documentation/test_results.json.

Hanya memakai standard library, jadi bisa dipakai untuk server lokal maupun
container Docker (server harus sudah jalan):

    python tests/run_scenarios.py --label lokal
    python tests/run_scenarios.py --label docker --base-url http://localhost:8000

Catatan: di Windows, "localhost" menambah sekitar 2 detik per request (urllib
mencoba IPv6 dulu). Pakai --base-url http://127.0.0.1:8000 supaya kolom waktu
hanya mengukur waktu server.
"""

import argparse
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "documentation" / "test_results"

# (jenis, query, intent yang diharapkan)
SKENARIO = [
    ("RAG", "Berapa jatah cuti tahunan saya?", "faq"),
    ("RAG", "Gimana cara reset password VPN kantor?", "faq"),
    ("Tool", "Tolong cek status tiket TICKET-0005 saya", "ticket_status"),
    ("Tool (tidak ada)", "Apa status tiket TICKET-0042 saya?", "ticket_status"),
    ("Di luar cakupan", "Siapa pemenang Piala Dunia 2022?", "unknown"),
    (
        "Tambahan, ambigu tanpa nomor",
        "Tiket saya kok belum selesai ya?",
        "ticket_status",
    ),
    ("Tambahan, parafrase", "Kalau WFH boleh berapa hari seminggu?", "faq"),
    ("Tambahan, format bebas", "status ticket 7 dong", "ticket_status"),
    (
        "Tambahan, topik HR tidak ada di KB",
        "Berapa besar THR yang saya dapat tahun ini?",
        "faq",
    ),
    (
        "Tambahan, ambigu laporan kerusakan",
        "Laptop saya rusak, harus lapor ke mana?",
        "faq",
    ),
]


def wait_for_health(base_url: str, timeout: int = 60) -> None:
    """Tunggu /health menjawab ok; server yang baru start butuh waktu membangun index."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=5) as response:
                if json.load(response).get("status") == "ok":
                    return
        except (OSError, http.client.HTTPException, ValueError):
            # container yang baru start bisa menutup koneksi (ConnectionResetError),
            # urllib tidak membungkusnya jadi URLError
            pass
        time.sleep(2)
    sys.exit(f"Server di {base_url} tidak siap dalam {timeout} detik")


def post_ask(base_url: str, query: str) -> tuple[int, dict]:
    """Kirim query ke /ask. Mengembalikan (kode HTTP, body); kode 0 jika tidak terhubung."""
    request = urllib.request.Request(
        f"{base_url}/ask",
        data=json.dumps({"query": query}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as err:
        # 422/503/500 tetap membawa body yang perlu dicatat
        try:
            return err.code, json.load(err)
        except ValueError:
            return err.code, {}
    except (OSError, http.client.HTTPException, ValueError) as err:
        return 0, {"status": "error", "intent": "-", "data": str(err)}


def run_scenario(no: int, base_url: str, skenario: tuple) -> dict:
    jenis, query, expected = skenario
    start = time.perf_counter()
    code, body = post_ask(base_url, query)
    elapsed = time.perf_counter() - start
    intent = body.get("intent", "-")
    return {
        "no": no,
        "jenis": jenis,
        "query": query,
        "intent_harapan": expected,
        "intent_hasil": intent,
        "http": code,
        "status": body.get("status", "-"),
        "data": str(body.get("data", body.get("detail", ""))),
        "waktu_detik": round(elapsed, 2),
        "sesuai": code == 200 and intent == expected,
    }


def _cell(value) -> str:
    """Aman untuk sel tabel markdown: tanpa newline dan tanpa tanda |."""
    return str(value).replace("\n", " ").replace("|", "\\|")


def render_markdown(rows: list[dict], label: str, base_url: str) -> str:
    lines = [
        f"# Hasil pengujian skenario ({label})",
        "",
        f"Dijalankan {datetime.now():%Y-%m-%d %H:%M} ke `{base_url}`. "
        "Cara menjalankan ulang: "
        f"`python tests/run_scenarios.py --label {label}` "
        "(server harus sudah jalan, atau pakai `--base-url`).",
        "",
        "| No | Jenis | Query | Intent harapan | Intent hasil | Status "
        "| Jawaban/Data | Waktu (s) | Sesuai? |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        status = r["status"] if r["http"] == 200 else f"{r['status']} (HTTP {r['http']})"
        lines.append(
            "| "
            + " | ".join(
                _cell(v)
                for v in (
                    r["no"],
                    r["jenis"],
                    r["query"],
                    r["intent_harapan"],
                    r["intent_hasil"],
                    status,
                    r["data"],
                    f"{r['waktu_detik']:.2f}",
                    "Ya" if r["sesuai"] else "Tidak",
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def print_table(rows: list[dict]) -> None:
    print(f"{'No':>2}  {'Harapan':<13} {'Hasil':<13} {'HTTP':>4} {'Status':<9} {'Detik':>6}  Ok  Query")
    for r in rows:
        print(
            f"{r['no']:>2}  {r['intent_harapan']:<13} {r['intent_hasil']:<13} "
            f"{r['http']:>4} {r['status']:<9} {r['waktu_detik']:>6.2f}  "
            f"{'Ya' if r['sesuai'] else '--':<3} {r['query']}"
        )
        print(f"    -> {r['data'][:110]}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Jalankan skenario uji ke /ask")
    parser.add_argument(
        "--base-url", default=os.getenv("BASE_URL", "http://localhost:8000")
    )
    parser.add_argument("--label", default="lokal", help="misal: lokal atau docker")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="path hasil tanpa ekstensi (.md dan .json ditambahkan otomatis)",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    wait_for_health(base_url)
    rows = [run_scenario(no, base_url, s) for no, s in enumerate(SKENARIO, start=1)]
    print_table(rows)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(".md").write_text(
        render_markdown(rows, args.label, base_url), encoding="utf-8"
    )
    args.out.with_suffix(".json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sesuai = sum(r["sesuai"] for r in rows)
    print(f"\n{sesuai}/{len(rows)} intent sesuai. Hasil: {args.out}.md / .json")
    return 0 if sesuai == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
