# Hasil pengujian skenario (docker)

Dijalankan 2026-10-28 22:41 ke `http://127.0.0.1:8000`. Cara menjalankan ulang: `python tests/run_scenarios.py --label docker` (server harus sudah jalan, atau pakai `--base-url`).

| No | Jenis | Query | Intent harapan | Intent hasil | Status | Jawaban/Data | Waktu (s) | Sesuai? |
|---|---|---|---|---|---|---|---|---|
| 1 | RAG | Berapa jatah cuti tahunan saya? | faq | faq | success | Karyawan tetap mendapatkan jatah 12 hari cuti tahunan yang dapat diambil setelah masa kerja minimal 3 bulan. Anda juga dapat melihat sisa cuti secara real-time melalui portal HR pada menu Ringkasan Cuti Saya. | 6.25 | Ya |
| 2 | RAG | Gimana cara reset password VPN kantor? | faq | faq | success | Halo! Kamu bisa melakukan reset password VPN secara mandiri melalui portal self-service IT. Jika akun kamu terkunci, silakan hubungi tim IT Support untuk bantuan lebih lanjut. | 4.67 | Ya |
| 3 | Tool | Tolong cek status tiket TICKET-0005 saya | ticket_status | ticket_status | success | Tiket TICKET-0005 (Reset password VPN gagal terus, kategori Access) atas nama Dedi Kurniawan saat ini berstatus Diproses. Update terakhir: 2026-08-27. | 0.01 | Ya |
| 4 | Tool (tidak ada) | Apa status tiket TICKET-0042 saya? | ticket_status | ticket_status | not_found | Tiket TICKET-0042 tidak ditemukan. Periksa kembali nomor tiketnya (format TICKET-XXXX). | 0.00 | Ya |
| 5 | Di luar cakupan | Siapa pemenang Piala Dunia 2022? | unknown | unknown | error | Maaf, permintaan ini di luar cakupan helpdesk People & IT. Saya bisa membantu pertanyaan kebijakan HR/IT atau cek status tiket (contoh: TICKET-0005). | 1.72 | Ya |
| 6 | Tambahan, ambigu tanpa nomor | Tiket saya kok belum selesai ya? | ticket_status | ticket_status | error | Nomor tiket belum disebutkan. Tuliskan nomornya, contoh: TICKET-0005. | 1.92 | Ya |
| 7 | Tambahan, parafrase | Kalau WFH boleh berapa hari seminggu? | faq | faq | success | Karyawan diperbolehkan bekerja dari rumah maksimal 2 hari per minggu. Pastikan jadwal tersebut sudah sesuai dengan kesepakatan dengan atasan masing-masing tim ya. | 4.84 | Ya |
| 8 | Tambahan, format bebas | status ticket 7 dong | ticket_status | ticket_status | success | Tiket TICKET-0007 (Permintaan monitor eksternal, kategori Hardware) atas nama Agus Setiawan saat ini berstatus Menunggu Persetujuan. Update terakhir: 2026-08-24. | 0.01 | Ya |
| 9 | Tambahan, topik HR tidak ada di KB | Berapa besar THR yang saya dapat tahun ini? | faq | faq | success | Maaf, informasi tersebut belum ada di knowledge base helpdesk. Silakan hubungi tim People & IT Operations melalui tiket IT. | 9.73 | Ya |
| 10 | Tambahan, ambigu laporan kerusakan | Laptop saya rusak, harus lapor ke mana? | faq | faq | success | Halo! Jika laptop kerja kamu rusak, silakan laporkan melalui tiket IT dengan kategori 'Hardware Issue' dan sertakan deskripsi masalahnya agar tim dapat memberikan unit pengganti sementara jika diperlukan. | 19.95 | Ya |

Catatan retrieval (dari `docker logs helpdesk`, FAQ id dengan skor cosine):

- No 1: FAQ 1 (0.8016), 7 (0.7615), 6 (0.7583).
- No 2: FAQ 8 (0.8213), 12 (0.7459), 13 (0.7368).
- No 7: FAQ 25 (0.7784), 26 (0.7234), 28 (0.6781).
- No 9: FAQ 20 (0.6938), 6 (0.6883), 1 (0.6667). Di bawah `MIN_SCORE` 0.73, jadi `NO_ANSWER` tanpa panggilan LLM untuk jawaban.
- No 10: FAQ 15 (0.7963), 14 (0.7191), 12 (0.7044).
- No 3, 4, 8: intent dari regex nomor tiket, tanpa LLM. No 5 dan 6: intent dari LLM, tanpa retrieval.

Model: `gemini-3-flash-preview` menjawab semua panggilan sampai skenario 8. Mulai skenario 9 model itu membalas 429, jadi panggilan pindah ke `gemini-3.5-flash-lite`.
