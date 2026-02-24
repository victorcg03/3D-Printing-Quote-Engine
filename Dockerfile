# Machine Shop Suite - 3D Printing Quote Engine
FROM public.ecr.aws/docker/library/python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget ca-certificates \
    gosu \
    libgl1 \
    libglu1-mesa \
    libegl1 \
    libgles2 \
    libglib2.0-0 \
    libgtk-3-0 \
    libgdk-pixbuf-2.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxi6 \
    libxrandr2 \
    libxcursor1 \
    libxdamage1 \
    libxfixes3 \
    libxcomposite1 \
    libxinerama1 \
    libsm6 \
    libice6 \
    libfontconfig1 \
    libfreetype6 \
  && rm -rf /var/lib/apt/lists/*
  # PrusaSlicer (AppImage) -> extract (no FUSE)
  RUN wget -q https://github.com/prusa3d/PrusaSlicer/releases/download/version_2.7.4/PrusaSlicer-2.7.4+linux-x64-GTK3-202404050928.AppImage \
  -O /usr/local/bin/PrusaSlicer.AppImage \
  && chmod +x /usr/local/bin/PrusaSlicer.AppImage \
  && cd /usr/local/bin \
  && ./PrusaSlicer.AppImage --appimage-extract \
  && ln -s /usr/local/bin/squashfs-root/usr/bin/prusa-slicer /usr/local/bin/prusa-slicer \
  && rm /usr/local/bin/PrusaSlicer.AppImage
  
  WORKDIR /app
  
  # Python deps
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  
  # App code
  COPY app.py .
  COPY config.py .
  COPY utils.py .
  COPY templates/ ./templates/
  COPY static/ ./static/
  COPY quotes_store.py .
  COPY security.py .
  
  # Non-root user
  RUN useradd -m -u 1000 -s /bin/bash appuser \
  && mkdir -p /app/logs /app/data \
  && chown -R appuser:appuser /app
  
  RUN ldd /usr/local/bin/squashfs-root/usr/bin/bin/prusa-slicer | grep "not found" || true
# Entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Run entrypoint as root (to chown volumes), then drop privileges
USER root
ENTRYPOINT ["/entrypoint.sh"]

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:5000/api/config', timeout=5)" || exit 1

CMD ["gosu", "appuser:appuser", "gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "app:app"]