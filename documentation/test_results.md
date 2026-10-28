# Hasil pengujian skenario (lokal)

Dijalankan 2026-10-28 22:17 ke `http://127.0.0.1:8000`. Cara menjalankan ulang: `python tests/run_scenarios.py --label lokal` (server harus sudah jalan, atau pakai `--base-url`).

| No | Jenis | Query | Intent harapan | Intent hasil | Status | Jawaban/Data | Waktu (s) | Sesuai? |
|---|---|---|---|---|---|---|---|---|
| 1 | RAG | Berapa jatah cuti tahunan saya? | faq | faq | success | Halo! Sebagai karyawan tetap, Anda mendapat jatah 12 hari cuti tahunan yang dapat diambil setelah masa kerja minimal 3 bulan. Anda juga bisa melihat sisa cuti secara real-time melalui portal HR pada menu Ringkasan Cuti Saya. | 22.28 | Ya |
| 2 | RAG | Gimana cara reset password VPN kantor? | faq | faq | success | Halo! Reset password VPN dapat kamu lakukan secara mandiri melalui portal self-service IT, atau kamu bisa menghubungi tim IT Support jika akunmu terkunci. | 23.44 | Ya |
| 3 | Tool | Tolong cek status tiket TICKET-0005 saya | ticket_status | ticket_status | success | Tiket TICKET-0005 (Reset password VPN gagal terus, kategori Access) atas nama Dedi Kurniawan saat ini berstatus Diproses. Update terakhir: 2026-08-27. | 0.01 | Ya |
| 4 | Tool (tidak ada) | Apa status tiket TICKET-0042 saya? | ticket_status | ticket_status | not_found | Tiket TICKET-0042 tidak ditemukan. Periksa kembali nomor tiketnya (format TICKET-XXXX). | 0.00 | Ya |
| 5 | Di luar cakupan | Siapa pemenang Piala Dunia 2022? | unknown | unknown | error | Maaf, permintaan ini di luar cakupan helpdesk People & IT. Saya bisa membantu pertanyaan kebijakan HR/IT atau cek status tiket (contoh: TICKET-0005). | 15.27 | Ya |
| 6 | Tambahan, ambigu tanpa nomor | Tiket saya kok belum selesai ya? | ticket_status | ticket_status | error | Nomor tiket belum disebutkan. Tuliskan nomornya, contoh: TICKET-0005. | 11.01 | Ya |
| 7 | Tambahan, parafrase | Kalau WFH boleh berapa hari seminggu? | faq | faq | success | Halo! Karyawan dapat bekerja dari rumah maksimal 2 hari per minggu sesuai kesepakatan dengan atasan masing-masing tim. | 35.66 | Ya |
| 8 | Tambahan, format bebas | status ticket 7 dong | ticket_status | ticket_status | success | Tiket TICKET-0007 (Permintaan monitor eksternal, kategori Hardware) atas nama Agus Setiawan saat ini berstatus Menunggu Persetujuan. Update terakhir: 2026-08-24. | 0.00 | Ya |
| 9 | Tambahan, topik HR tidak ada di KB | Berapa besar THR yang saya dapat tahun ini? | faq | faq | success | Maaf, informasi tersebut belum ada di knowledge base helpdesk. Silakan hubungi tim People & IT Operations melalui tiket IT. | 14.46 | Ya |
| 10 | Tambahan, ambigu laporan kerusakan | Laptop saya rusak, harus lapor ke mana? | faq | faq | success | Halo! Jika laptop kerja kamu rusak, kamu bisa melaporkannya melalui tiket IT dengan kategori 'Hardware Issue' dan sertakan deskripsi masalahnya agar tim dapat memberikan unit pengganti sementara jika diperlukan. | 24.70 | Ya |

## Catatan retrieval

Diambil dari log server pada run di atas (format: faq_id dengan skor cosine, urut dari yang tertinggi; `MIN_SCORE` = 0.73).

- No 1: FAQ 1 (0.8016), 7 (0.7615), 6 (0.7583).
- No 2: FAQ 8 (0.8213), 12 (0.7459), 13 (0.7368).
- No 7: FAQ 25 (0.7784), 26 (0.7234), 28 (0.6781).
- No 9: FAQ 20 (0.6938), 6 (0.6883), 1 (0.6667). Skor teratas di bawah `MIN_SCORE`, jadi langsung `NO_ANSWER` tanpa memanggil LLM untuk jawaban. LLM hanya dipanggil untuk intent.
- No 10: FAQ 15 (0.7963), 14 (0.7191), 12 (0.7044).
- No 5 dan 6: tidak ada retrieval. Intent `unknown` / `ticket_status` dari LLM. No 6 tidak punya nomor tiket sehingga tool tidak dipanggil.
- No 3, 4, 8: intent dari regex nomor tiket, tidak ada panggilan LLM.

Pada run ini `gemini-3.8-flash` dan `gemini-3.6-flash` menjawab 429 (kuota free tier 20 request per hari per model habis karena beberapa kali run sebelumnya), sehingga fallback jatuh ke `gemini-3.5-flash-lite`. Semua intent dan jawaban di atas berasal dari model itu. Pada run sebelumnya hari yang sama `gemini-3.8-flash` masih sering 503 dan `gemini-3.6-flash` yang menjawab.

Waktu FAQ 14-36 detik hampir seluruhnya berasal dari dua panggilan LLM berantai (intent lalu jawaban) ditambah percobaan model yang gagal. Retrieval sendiri sekitar 0.5 detik.
