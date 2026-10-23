FROM node:22-bookworm-slim AS node-runtime
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
WORKDIR /srv/video-saas
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY app ./app
COPY static ./static
RUN addgroup --system app && adduser --system --ingroup app app && mkdir -p data downloads && chown -R app:app /srv/video-saas
USER app
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--workers","1","--proxy-headers","--forwarded-allow-ips","*"]
