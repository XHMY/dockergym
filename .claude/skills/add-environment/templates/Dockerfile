# Replace <env_name> and <target_package> with actual values.
# Choose the Python version that matches the target environment's requirements.
#
# IMPORTANT: The build context must be the repo root so COPY can access
# dockergym/worker.py. Build with:
#   docker build -t <env_name>:latest -f dockergym/envs/<env_name>/Dockerfile .

FROM python:3.9-slim
WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dockergym BaseWorker (minimal — only stdlib, no extra dependencies)
COPY dockergym/worker.py /app/dockergym/
RUN printf 'from dockergym.worker import BaseWorker\n__all__ = ["BaseWorker"]\n' > /app/dockergym/__init__.py
ENV PYTHONPATH=/app

# Install target environment
# For PyPI packages:
#   RUN pip install --no-cache-dir <target_package>
# For GitHub repos:
#   RUN pip install --no-cache-dir "<target_package> @ git+https://github.com/<org>/<repo>.git"
# For repos with extras:
#   RUN pip install --no-cache-dir "<target_package>[extra] @ git+https://github.com/<org>/<repo>.git"
RUN pip install --no-cache-dir <target_package>

# Set environment variables (if needed)
# ENV DATA_DIR=/data

# Create data directories (if needed)
# RUN mkdir -p /data

# Verification command (overridden at runtime by worker_command)
CMD ["python", "-c", "import <target_package>; print('<EnvName> ready!')"]
