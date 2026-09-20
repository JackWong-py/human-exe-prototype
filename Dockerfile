FROM python:3.12-slim

# Tesseract reads the scanned PDFs (member C's scan reader).
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Only what the running app needs. Secrets (.env) are NOT copied: pass them at run time.
COPY app ./app
COPY contracts.py loader.py ./
COPY data ./data

ENV DB_PATH=/db/sdoc.db \
    AUTO_RUN=1
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
