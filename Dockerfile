FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# (Part-2/3 me ffmpeg/pymupdf etc add karenge. Abhi minimal.)

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# Render sets PORT
EXPOSE 10000

CMD ["python", "app.py"]
