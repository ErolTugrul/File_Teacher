FROM python:3.12-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y \
libreoffice \
fonts-liberation \
libgomp1 \
libfontconfig1 \
&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/temp_files && chmod 777 /app/temp_files

COPY . .