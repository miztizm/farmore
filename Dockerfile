# Farmore Docker Image
# Multi-stage build for minimal image size
#
# "Containers are just VMs with commitment issues. But faster." — schema.cx

# Build stage
FROM python:3.12-alpine AS builder

# Install build dependencies
RUN apk add --no-cache \
    git \
    git-lfs \
    openssh-client \
    build-base

# Initialize git-lfs
RUN git lfs install --system

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install farmore
WORKDIR /app
COPY pyproject.toml README.md ./
COPY farmore/ farmore/
RUN pip install --no-cache-dir .

# Runtime stage
FROM python:3.12-alpine

# Install runtime dependencies
RUN apk add --no-cache \
    git \
    git-lfs \
    openssh-client \
    && git lfs install --system

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set up SSH directory for SSH key mounting
RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh

# Set working directory for backups
WORKDIR /backups

# Create volume mount points
VOLUME ["/backups", "/root/.ssh"]

# Default environment variable (can be overridden)
ENV GITHUB_TOKEN=""
ENV GITHUB_HOST=""

# Labels
LABEL org.opencontainers.image.title="Farmore"
LABEL org.opencontainers.image.description="Mirror every repo you own — in one command"
LABEL org.opencontainers.image.url="https://github.com/miztizm/farmore"
LABEL org.opencontainers.image.source="https://github.com/miztizm/farmore"
LABEL org.opencontainers.image.version="0.4.0"
LABEL org.opencontainers.image.licenses="MIT"

# Default command (show help)
ENTRYPOINT ["farmore"]
CMD ["--help"]
