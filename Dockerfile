FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    TIMEZONE=America/Bogota \
    REPORTS_DIR=/data/reports

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tzdata libfreetype6 libpng16-16 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 curu \
    && mkdir -p /data/reports \
    && chown -R curu:curu /app /data

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY --chown=curu:curu . .
USER curu

VOLUME ["/data"]
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=3)" || exit 1

CMD ["python", "bot.py"]
