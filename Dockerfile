FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \           # 👈 THIS LINE fixes the libGL.so.1 error
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:8000"]
