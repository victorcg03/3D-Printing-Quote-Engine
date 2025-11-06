# Machine Shop Suite - 3D Printing Quote Engine
# Multi-stage Docker build for production

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies and PrusaSlicer
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download and install PrusaSlicer (AppImage)
# Note: You may need to update the version number
RUN wget https://github.com/prusa3d/PrusaSlicer/releases/download/version_2.7.0/PrusaSlicer-2.7.0+linux-x64-GTK3-202311210847.AppImage \
    -O /usr/local/bin/PrusaSlicer.AppImage \
    && chmod +x /usr/local/bin/PrusaSlicer.AppImage

# Extract AppImage (since AppImage needs FUSE which doesn't work well in Docker)
RUN cd /usr/local/bin \
    && ./PrusaSlicer.AppImage --appimage-extract \
    && ln -s /usr/local/bin/squashfs-root/usr/bin/prusa-slicer /usr/local/bin/prusa-slicer \
    && rm PrusaSlicer.AppImage

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY config.py .
COPY utils.py .
COPY templates/ ./templates/
COPY static/ ./static/

# Create necessary directories
RUN mkdir -p logs

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/api/config', timeout=5)" || exit 1

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
