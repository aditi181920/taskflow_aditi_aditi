# Stage 1: Build — install dependencies into a virtual env
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


# Stage 2: Runtime — minimal image with only what's needed
FROM python:3.12-slim AS runtime

# Security: run as non-root user
RUN groupadd -r taskflow && useradd -r -g taskflow taskflow

WORKDIR /app

# Copy the pre-built virtual env from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

USER taskflow

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
