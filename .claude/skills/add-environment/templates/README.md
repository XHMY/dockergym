# <EnvName> Environment for DockerGym

This package provides a ready-to-run [<EnvName>](<link_to_env_repo>) environment on top of DockerGym.

Use this README for <EnvName>-specific setup and behavior. For shared DockerGym API endpoints and worker protocol, see the root [`README.md`](../../../README.md).

## What runs where

- The API server runs on the host (`python -m dockergym.envs.<env_name>`).
- Each session gets its own Docker container running `worker.py`.
- Data is mounted from host storage into containers at `/data`.

## First successful run

### 1) Build the <EnvName> worker image (one-time)

```bash
REPO_ROOT=$(python -c "import dockergym, os; print(os.path.dirname(os.path.dirname(dockergym.__file__)))")
docker build -t <env_name>:latest -f "$REPO_ROOT/dockergym/envs/<env_name>/Dockerfile" "$REPO_ROOT"
```

### 2) Download/prepare data (if needed)

```bash
# Example: download data using the Docker image
# docker run --rm -v ~/.cache/<env_name>:/data <env_name>:latest \
#   bash -c "<download_command>"
```

### 3) Start the API server

```bash
python -m dockergym.envs.<env_name> \
  --port 8000
```

### 4) Verify startup

```bash
curl http://localhost:8000/health
curl http://localhost:8000/environments
```

In `/health`, `available_environments` should be greater than `0`.

### 5) Run the bundled example client

In another terminal:

```bash
python -m dockergym.envs.<env_name>.example \
  --base-url http://localhost:8000 \
  --concurrent 8 \
  --total-jobs 20
```

## Environment-specific session behavior

`POST /sessions` accepts:

```bash
# Let the server pick a random environment:
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{}'

# Specify a particular environment:
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"env_id": "<some_env_id>"}'
```

## CLI options

```bash
python -m dockergym.envs.<env_name> \
  --docker-image <env_name>:latest \
  --max-sessions 64 \
  --batch-window-ms 50 \
  --idle-timeout 120 \
  --host 0.0.0.0 \
  --port 8000
```

## Troubleshooting

- `available_environments` is `0`:
  - Data is missing or the volume mount points to the wrong path.
- `docker: Error response from daemon: pull access denied for <env_name>`:
  - Re-run the image build step.
- Need cleanup after interruption:
  - Run `curl -X DELETE http://localhost:8000/sessions`.

Swagger docs are available at `http://localhost:8000/docs`.
