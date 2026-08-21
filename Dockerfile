# ── Stage 1: 构建 React 前端 ──
FROM node:20-alpine AS web-builder
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
# 同源部署：base 留空 → 前端 API 走相对路径（与后端同源）
ENV REACT_APP_API_BASE_URL=
RUN npm run build

# ── Stage 2: Python 后端 + 托管前端 ──
FROM python:3.12-slim
WORKDIR /app
COPY server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY server/app ./app
COPY --from=web-builder /web/build ./web_build
ENV INSIGHT_DATABASE=/data/insight.db
ENV INSIGHT_WEB_BUILD=/app/web_build
VOLUME ["/data"]
EXPOSE 8080
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers
