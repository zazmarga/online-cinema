FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app


COPY . /app


RUN pip install --no-cache-dir -r requirements.txt


ENV PYTHONPATH=/app/src

EXPOSE 8000
