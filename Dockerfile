# ClauseLens 后端 + 前端静态资源，一个镜像全包
#
# 默认构建（约 450 MB，不含浏览器渲染）：
#   docker build -t clauselens .
# 带 SPA 渲染（约 1.2 GB，含 Chromium，能处理 cloud.doulor.cn 那种纯前端路由站）：
#   docker build --build-arg WITH_RENDER=1 -t clauselens .
#
# 运行：
#   docker run -p 8787:8787 -e CLAUSELENS_EGRESS=instabox:<machine-id> clauselens
#
# 注意：模型和 registry 是运行时必需的数据（39 MB + 13.5 MB），这里直接 COPY 进镜像，
# 换数据要重新构建；如果改成挂载卷，记得 models/ 和 processed/registry.json 都在。

FROM python:3.14-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# lxml 需要 libxml2/libxslt；curl 用于健康检查
RUN apt-get update && apt-get install -y --no-install-recommends \
        libxml2 libxslt1.1 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖，利用层缓存
COPY requirements.txt .
# 国内机器直连 pypi 常超时，默认走清华镜像（海外部署时改成官方源即可）
ARG PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --no-cache-dir -i ${PIP_INDEX} -r requirements.txt

# 代码与运行数据
COPY backend/ ./backend/
COPY data/models/ ./data/models/
COPY data/processed/registry.json ./data/processed/registry.json
# 前端可选：B 方案里页面由 Cloudflare Pages 托管，API 容器不需要 dist。
# api.py 里 `if DIST.exists()` 会自动跳过静态挂载，所以 dist 不存在也能跑。
COPY frontend/ ./frontend/
RUN mkdir -p frontend/dist || true

# ── 可选：SPA 渲染（Chromium）──────────────────────────────────────
ARG WITH_RENDER=0
RUN if [ "$WITH_RENDER" = "1" ]; then \
        pip install --no-cache-dir playwright==1.64.1 && \
        playwright install --with-deps chromium && \
        rm -rf /root/.cache/ms-playwright/*.zip ; \
    fi

ENV CLAUSELENS_MAX_RENDERS=3 \
    CLAUSELENS_RENDER_TIMEOUT_MS=25000

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD curl -fsS http://127.0.0.1:8787/api/taxonomy > /dev/null || exit 1

# 单进程即可；uvicorn 自带线程池，pipeline 内部也有并发探测
CMD ["python", "-m", "uvicorn", "clauselens.api:app", \
     "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8787", \
     "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]

