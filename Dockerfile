# Pola dari Sesi 14.2: FROM python -> WORKDIR -> COPY -> RUN pip -> CMD.
# Pakai 3.13 (sama dengan dev lokal); numpy/pandas yang di-pin butuh Python >= 3.11/3.12.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# copy requirements dulu supaya layer install ter-cache selama dependency tidak berubah
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# hanya source dan data; API key tidak dimasukkan ke image,
# kirim saat run: docker run --env-file .env -p 8000:8000 <image>
COPY app/ app/
COPY data/ data/

# jalankan sebagai user biasa, bukan root
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
