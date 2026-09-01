FROM python:3.10-slim

WORKDIR /app

# Get full logs in case of crash and don't store bytecode on disk
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install required pip modules
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy code into the container
COPY backend /app/backend
COPY frontend /app/frontend

EXPOSE 8000

CMD ["python", "-m", "backend.main"]
