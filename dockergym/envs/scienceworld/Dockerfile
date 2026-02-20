FROM python:3.11-slim
WORKDIR /app

# Install Java (required by ScienceWorld's Scala backend via py4j)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jdk \
    && rm -rf /var/lib/apt/lists/*

# Install dockergym BaseWorker (minimal — only stdlib, no extra dependencies)
COPY dockergym/worker.py /app/dockergym/
RUN printf 'from dockergym.worker import BaseWorker\n__all__ = ["BaseWorker"]\n' > /app/dockergym/__init__.py
ENV PYTHONPATH=/app

# Install ScienceWorld (ships a bundled JAR — no data download needed)
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    pip install --no-cache-dir scienceworld

# Verification command (overridden at runtime by worker_command)
CMD ["python", "-c", "from scienceworld import ScienceWorldEnv; print('ScienceWorld ready!')"]
