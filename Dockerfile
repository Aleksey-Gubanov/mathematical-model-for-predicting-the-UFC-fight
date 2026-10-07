FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    MMA_DEBUG=false \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]