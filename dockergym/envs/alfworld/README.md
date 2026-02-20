# ALFWorld Environment for DockerGym

This package provides a ready-to-run [ALFWorld](https://github.com/alfworld/alfworld) environment on top of DockerGym.

Use this README for ALFWorld-specific setup and behavior. For shared DockerGym API endpoints and worker protocol, see the root [`README.md`](../../../README.md).

## What runs where

- The API server runs on the host (`python -m dockergym.envs.alfworld`).
- Each session gets its own Docker container running `worker.py`.
- ALFWorld data is mounted from host storage into containers at `/data`.

## First successful run

### 1) Build the ALFWorld worker image (one-time)

```bash
DOCKERFILE_DIR=$(python -c "import dockergym.envs.alfworld, os; print(os.path.dirname(dockergym.envs.alfworld.__file__))")
docker build -t alfworld-text:latest "$DOCKERFILE_DIR"
```

### 2) Download ALFWorld data (one-time)

```bash
docker run --rm -v ~/.cache/alfworld:/data alfworld-text:latest \
  bash -lc "alfworld-download"
```

### 3) Start the API server

```bash
python -m dockergym.envs.alfworld \
  --data-volume ~/.cache/alfworld:/data:ro \
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
python -m dockergym.envs.alfworld.example \
  --base-url http://localhost:8000 \
  --concurrent 24 \
  --total_jobs 100
```

The example runs many short episodes in parallel and automatically deletes each session after use.

## ALFWorld-specific session behavior

`POST /sessions` supports two useful patterns:

1. Let the server pick a random game:

```bash
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{}'
```

2. Filter random selection by ALFWorld task type:

```bash
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"params": {"task_type": 1}}'
```

Task type mapping:

| ID | Name |
|----|------|
| `1` | `pick_and_place_simple` |
| `2` | `look_at_obj_in_light` |
| `3` | `pick_clean_then_place_in_recep` |
| `4` | `pick_heat_then_place_in_recep` |
| `5` | `pick_cool_then_place_in_recep` |
| `6` | `pick_two_obj_and_place` |

If you pass `env_id`, that exact game file is used and `task_type` is ignored.

## CLI options

```bash
python -m dockergym.envs.alfworld \
  --config base_config.yaml \
  --docker-image alfworld-text:latest \
  --data-volume ~/.cache/alfworld:/data:ro \
  --max-sessions 64 \
  --batch-window-ms 50 \
  --idle-timeout 120 \
  --host 0.0.0.0 \
  --port 8000
```

Notes:

- `--config` points to ALFWorld dataset paths and enabled `task_types`.
- `--data-volume` host path should contain `json_2.1.1/...` folders.
- `--max-sessions` should be tuned to your CPU and memory budget.

## Troubleshooting

- `available_environments` is `0`:
  - Data is missing, or `--data-volume` points to the wrong host path.
  - Check that `~/.cache/alfworld/json_2.1.1` exists.
- `docker: Error response from daemon: pull access denied for alfworld-text`:
  - Re-run the image build step.
- Need cleanup after interruption:
  - Run `curl -X DELETE http://localhost:8000/sessions`.

Swagger docs are available at `http://localhost:8000/docs`.
