# Etapa 1: Build
FROM python:3.13-slim AS builder

# Variáveis de ambiente para o build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=development \
    NPM_BIN_PATH=/usr/bin/npm \
    DJANGO_SETTINGS_MODULE=webapp.settings \
    DEBUG=False

WORKDIR /app

# Instalar dependências do sistema e Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt


COPY . .

# Instalar dependências do Node.js e compilar Tailwind
WORKDIR /app/app/theme/static_src
RUN npm install --include=dev && npm run build

WORKDIR /app/app
RUN python manage.py collectstatic --noinput --skip-checks

# Etapa 2: Imagem final
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt && pip install gunicorn

COPY --from=builder /app /app

RUN echo '#!/bin/bash\ncd /app/app\npython manage.py migrate\nexec gunicorn webapp.wsgi:application --bind 0.0.0.0:8000' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

EXPOSE 8000

CMD ["/app/entrypoint.sh"]