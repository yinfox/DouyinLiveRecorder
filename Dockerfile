FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    MALLOC_ARENA_MAX=2 \
    MALLOC_TRIM_THRESHOLD_=65536 \
    TZ=Asia/Shanghai \
    WEBUI_HOST=0.0.0.0 \
    WEBUI_PORT=8080

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
        fontconfig \
        fonts-noto-cjk \
        fonts-noto-color-emoji \
        fonts-symbola \
        nodejs \
        tzdata && \
    ln -fs /usr/share/zoneinfo/${TZ} /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --timeout 120 --retries 10 -r requirements.txt

COPY . /app

RUN mkdir -p /app/config /app/logs /app/backup_config /app/downloads

EXPOSE 8080

CMD ["python", "main.py"]
