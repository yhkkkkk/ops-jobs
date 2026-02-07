# Control-plane Dockerfile
FROM docker.1ms.run/ubuntu:22.04 AS frontend-builder

# Use Aliyun apt mirror
RUN sed -i 's@http://archive.ubuntu.com/ubuntu/@http://mirrors.aliyun.com/ubuntu/@g' /etc/apt/sources.list \
    && sed -i 's@http://security.ubuntu.com/ubuntu/@http://mirrors.aliyun.com/ubuntu/@g' /etc/apt/sources.list

# Install Node.js and pnpm
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g pnpm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Frontend workdir
WORKDIR /app/frontend

# Frontend build args/env (default to relative paths so requests follow page origin)
ARG VITE_API_BASE_URL=/api
ARG VITE_SSE_BASE_URL=/api/realtime/sse
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_SSE_BASE_URL=${VITE_SSE_BASE_URL}

# Configure pnpm to use Chinese registry for faster package installation
RUN pnpm config set registry https://registry.npmmirror.com

# Install frontend deps
COPY frontend/package*.json frontend/pnpm-lock.yaml ./
RUN pnpm install
RUN pnpm add -D terser

# Copy frontend source
COPY frontend/ ./

# Build frontend
RUN pnpm run build

# Static front serving stage with Nginx reverse proxy to control-plane
FROM docker.1ms.run/nginx:1.27-alpine AS frontend-static
RUN apk add --no-cache gettext
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf.template
# Defaults can be overridden at runtime via environment
ENV CONTROL_PLANE_HOST=control-plane
ENV CONTROL_PLANE_HTTP_PORT=8000
ENV CONTROL_PLANE_ASGI_PORT=8001
# 仅替换我们定义的环境变量，避免覆盖 Nginx 内置的 $host/$remote_addr 等
CMD ["sh", "-c", "envsubst '${CONTROL_PLANE_HOST} ${CONTROL_PLANE_HTTP_PORT} ${CONTROL_PLANE_ASGI_PORT}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"]

# Python app stage
FROM docker.1ms.run/ubuntu:22.04 AS python-builder

# Use Aliyun apt mirror
RUN sed -i 's@http://archive.ubuntu.com/ubuntu/@http://mirrors.aliyun.com/ubuntu/@g' /etc/apt/sources.list \
    && sed -i 's@http://security.ubuntu.com/ubuntu/@http://mirrors.aliyun.com/ubuntu/@g' /etc/apt/sources.list

# Set timezone to Asia/Shanghai
ENV TZ=Asia/Shanghai
RUN apt-get update && apt-get install -y tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python and system deps
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3-pip \
    curl \
    build-essential \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    libxml2-dev \
    libxslt-dev \
    libldap2-dev \
    libsasl2-dev \
    redis-server \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip3 install uv

# Install supervisor for process management
RUN apt-get update && apt-get install -y supervisor && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy Python deps
COPY pyproject.toml uv.lock ./

# Install Python deps (cached layer - only rebuilt when deps change)
RUN uv sync --frozen --no-install-project --no-cache

# Copy application code (rebuilt when app code changes, but deps layer is cached)
COPY apps/ ./apps/
COPY ops_job/ ./ops_job/
COPY utils/ ./utils/
COPY manage.py .
COPY gunicorn_config.py .
COPY docker/ ./docker/

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

# Copy docker configs (supervisor/nginx/entrypoint)
COPY docker/ /docker/
RUN chmod +x /docker/entrypoint.sh

# Required dirs
RUN mkdir -p /app/logs /app/media /app/staticfiles \
    && chown -R app:app /app/logs /app/media /app/staticfiles

# Switch user
USER app

# Expose ports
EXPOSE 8000 8001

# Healthcheck
HEALTHCHECK --interval=60s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Entrypoint to run migrations and start supervisor
ENTRYPOINT ["/docker/entrypoint.sh"]
