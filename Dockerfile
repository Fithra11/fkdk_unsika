FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    libssl-dev \
    libffi-dev \
    gcc \
    pkg-config \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

WORKDIR /app
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
