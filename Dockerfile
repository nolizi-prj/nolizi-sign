# syntax=docker/dockerfile:1

# ---- Stage 1: build the frontend SPA ----
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: backend runtime image ----
FROM python:3.12-slim-bookworm

# libreoffice-writer/-calc/-impress: docx/xlsx/pptx/ppt -> PDF conversion (see app/conversion.py).
# postgresql-client: pg_dump for the daily backup job (see app/routers/jobs.py).
# fonts-dejavu: consistent Latin/Cyrillic/Greek glyph coverage for LibreOffice-driven PDF conversion.
# fonts-noto-cjk: Korean/Japanese/Chinese glyphs — without it, CJK text in
#   converted documents renders as tofu boxes.
# fonts-noto-core: broad coverage for other non-Latin scripts (Arabic,
#   Hebrew, Thai, Devanagari, ...).
# fonts-nanum: TrueType Korean font for PDF stamping (app/stamping.py) —
#   reportlab can't embed the Noto CJK TTCs (PostScript/CFF outlines).
# fonts-liberation + fonts-crosextra-carlito/-caladea: metric-compatible
#   substitutes for the Microsoft fonts nearly every uploaded Office
#   document uses (Liberation → Arial/Times New Roman/Courier New,
#   Carlito → Calibri, Caladea → Cambria). Without them LibreOffice falls
#   back to fonts with different widths and the converted PDF reflows —
#   changed line breaks, apparent font-size/face changes.
#
# Debian bookworm's `postgresql-client` package is v15, but pg_dump refuses to
# dump a newer server (Railway's managed Postgres runs v18) — "aborting
# because of server version mismatch". The PGDG apt repo below provides a
# current postgresql-client package instead of the stale bookworm one.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
    > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    postgresql-client-18 \
    fonts-dejavu \
    fonts-noto-cjk \
    fonts-noto-core \
    fonts-nanum \
    fonts-liberation \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# Built SPA assets, served by FastAPI when frontend/dist exists (see app/main.py).
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

EXPOSE 8080

CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'
