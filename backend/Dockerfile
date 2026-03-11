FROM python:3.11-slim

WORKDIR /app

RUN echo ">>> [1/4] Installing system packages..." && \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/* && \
    echo ">>> System packages installed"

RUN echo ">>> [2/4] Installing Python dependencies (this may take a few minutes)..."
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt 2>&1 && echo ">>> Python dependencies installed"

RUN echo ">>> [3/4] Copying application files..."
COPY . .

RUN echo ">>> [4/4] Backend image ready"

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
