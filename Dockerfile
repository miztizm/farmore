# Farmore Docker Image
# Multi-stage build for minimal image size
#
# "Containers are just VMs with commitment issues. But faster." — schema.cx

# =============================================================================
# Build stage
# =============================================================================
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

# =============================================================================
# Runtime stage
# =============================================================================
FROM python:3.12-alpine

# Labels
LABEL org.opencontainers.image.title="Farmore"
LABEL org.opencontainers.image.description="Mirror every repo you own — in one command"
LABEL org.opencontainers.image.url="https://github.com/miztizm/farmore"
LABEL org.opencontainers.image.source="https://github.com/miztizm/farmore"
LABEL org.opencontainers.image.version="0.5.0"
LABEL org.opencontainers.image.licenses="MIT"
LABEL maintainer="miztizm <https://github.com/miztizm>"

# Install runtime dependencies
RUN apk add --no-cache \
    git \
    git-lfs \
    openssh-client \
    ca-certificates \
    tzdata \
    && git lfs install --system \
    && rm -rf /var/cache/apk/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN addgroup -g 1000 farmore \
    && adduser -u 1000 -G farmore -h /home/farmore -D farmore

# Set up directories with proper permissions
RUN mkdir -p /backups /home/farmore/.ssh \
    && chmod 700 /home/farmore/.ssh \
    && chown -R farmore:farmore /backups /home/farmore

# Set working directory for backups
WORKDIR /backups

# Create volume mount points
VOLUME ["/backups", "/home/farmore/.ssh"]

# Environment variables (can be overridden)
ENV GITHUB_TOKEN=""
ENV GITHUB_HOST=""
ENV TZ="UTC"

# Switch to non-root user
USER farmore

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD farmore --version || exit 1

# Default command (show help)
ENTRYPOINT ["farmore"]
CMD ["--help"]

# =============================================================================
# Usage Examples:
# =============================================================================
# Build the image:
#   docker build -t farmore .
#
# Run with environment token:
#   docker run -v $(pwd)/backups:/backups -e GITHUB_TOKEN=$GITHUB_TOKEN farmore user miztizm
#
# Run with SSH key:
#   docker run -v $(pwd)/backups:/backups -v ~/.ssh:/home/farmore/.ssh:ro farmore user miztizm
#
# GitHub Enterprise:
#   docker run -e GITHUB_TOKEN=$TOKEN -e GITHUB_HOST=github.mycompany.com farmore user me
#
# Backup gists:
#   docker run -v $(pwd)/backups:/backups -e GITHUB_TOKEN=$TOKEN farmore gists
#
# Interactive shell:
#   docker run -it --entrypoint /bin/sh farmore
# =============================================================================
