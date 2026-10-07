FROM python:3.13-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    --no-deps torch==2.9.1 \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-7007}"]
