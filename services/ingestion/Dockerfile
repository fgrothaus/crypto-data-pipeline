FROM python:3.11-slim

WORKDIR /app

# gcc installieren, da Python libs teilweise dependencies haben, die in C compiliert werden.
# anschließend die geladene Paketliste bei Installationserfolg wieder auf apt/lists löschen
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Von lokalen Ordner, wo der Dockerfile liegt, in das WORKDIR /app
COPY . .

CMD ["python", "ingestion_main.py"]