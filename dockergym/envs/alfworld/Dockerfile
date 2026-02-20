FROM python:3.9-slim
WORKDIR /app
RUN apt-get update && apt-get install -y git build-essential && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    pip install --no-cache-dir "textworld[pddl]>=1.6.1" pyyaml && \
    pip install --no-cache-dir "alfworld @ git+https://github.com/alfworld/alfworld.git"
ENV ALFWORLD_DATA=/data
RUN mkdir -p /data
CMD ["python", "-c", "import alfworld; print('ALFWorld ready!')"]
