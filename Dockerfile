FROM python:3.12-alpine

RUN apk add --no-cache ffmpeg

WORKDIR /app

COPY app/requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

EXPOSE 5000

# Local dev: run uvicorn directly, no HA/S6/bashio needed
# --reload watches for file changes (works with the volume mount in docker-compose)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000", "--reload"]