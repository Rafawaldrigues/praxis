FROM python:3.12-slim

WORKDIR /app

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY api/ ./api/
COPY models/ ./models/
COPY repositories/ ./repositories/
COPY database/ ./database/
COPY servicos/ ./servicos/
COPY frontend/ ./frontend/

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
