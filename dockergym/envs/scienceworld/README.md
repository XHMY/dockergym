# ScienceWorld Environment for DockerGym

This package provides a ready-to-run [ScienceWorld](https://github.com/allenai/ScienceWorld) environment on top of DockerGym. ScienceWorld is a text-based virtual environment for conducting elementary science experiments (boiling, melting, electrical conductivity, genetics, etc.) across 30 task types and ~6,700 variations.

Use this README for ScienceWorld-specific setup and behavior. For shared DockerGym API endpoints and worker protocol, see the root [`README.md`](../../../README.md).

## What runs where

- The **API server** runs on the host (`python -m dockergym.envs.scienceworld`).
- Each **session** gets its own Docker container running `worker.py`, which launches a JVM process (via py4j) hosting the ScienceWorld Scala simulator.
- **No data volumes** are needed — the ScienceWorld JAR and assets are bundled in the pip package inside the Docker image.

## First successful run

### 1) Build the ScienceWorld worker image (one-time)

```bash
REPO_ROOT=$(python -c "import dockergym, os; print(os.path.dirname(os.path.dirname(dockergym.__file__)))")
docker build -t scienceworld:latest -f "$REPO_ROOT/dockergym/envs/scienceworld/Dockerfile" "$REPO_ROOT"
```

### 2) Start the API server

```bash
python -m dockergym.envs.scienceworld --port 8000
```

### 3) Verify startup

```bash
curl http://localhost:8000/health
curl http://localhost:8000/environments
```

In `/health`, `available_environments` should be `30` (one per task type).

### 4) Run the bundled example client

In another terminal:

```bash
python -m dockergym.envs.scienceworld.example \
  --base-url http://localhost:8000 \
  --concurrent 8 \
  --total-jobs 20
```

## Environment-specific session behavior

`POST /sessions` accepts:

```bash
# Random task, random training variation:
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{}'

# Specific task:
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"env_id": "boil"}'

# Specific task + variation + simplifications:
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"env_id": "boil", "params": {"variation_idx": 0, "simplification_str": "easy", "env_step_limit": 50}}'
```

### Session creation params

| Param | Type | Default | Description |
|---|---|---|---|
| `variation_idx` | int | random (train set) | Variation index for the task |
| `simplification_str` | str | `""` | Comma-separated simplifications (e.g. `"easy"`, `"teleportAction,openDoors"`) |
| `env_step_limit` | int | `100` | Maximum steps per episode |
| `generate_gold_path` | bool | `false` | Whether to generate the gold action sequence |

### Info fields returned

Both the session creation response and each step response include an `info` dict:

| Field | Type | Description |
|---|---|---|
| `valid_actions` | list[str] | Currently valid action-object combinations |
| `score` | int | Cumulative score (0–100) |
| `task_description` | str | Natural language description of the goal |
| `look` | str | Current room description (free action) |
| `inventory` | str | Current inventory (free action) |
| `moves` | int | Number of moves taken so far |
| `task_name` | str | Task name (on init only) |
| `variation_idx` | int | Variation index (on init only) |

### Available tasks (30)

`boil`, `melt`, `freeze`, `change-the-state-of-matter-of`, `use-thermometer`, `measure-melting-point-known-substance`, `measure-melting-point-unknown-substance`, `power-component`, `power-component-renewable-vs-nonrenewable-energy`, `test-conductivity`, `test-conductivity-of-unknown-substances`, `find-living-thing`, `find-non-living-thing`, `find-plant`, `find-animal`, `grow-plant`, `grow-fruit`, `chemistry-mix`, `chemistry-mix-paint-secondary-color`, `chemistry-mix-paint-tertiary-color`, `lifespan-longest-lived`, `lifespan-shortest-lived`, `lifespan-longest-lived-then-shortest-lived`, `identify-life-stages-1`, `identify-life-stages-2`, `inclined-plane-determine-angle`, `inclined-plane-friction-named-surfaces`, `inclined-plane-friction-unnamed-surfaces`, `mendelian-genetics-known-plant`, `mendelian-genetics-unknown-plant`

## CLI options

```bash
python -m dockergym.envs.scienceworld \
  --docker-image scienceworld:latest \
  --max-sessions 1024 \
  --batch-window-ms 50 \
  --idle-timeout 120 \
  --host 0.0.0.0 \
  --port 8000
```

## Troubleshooting

- **`available_environments` is `0`**: This should not happen since task names are hardcoded. Check server logs for startup errors.
- **Container startup is slow**: The first step in a session launches a JVM inside the container. Allow 5–10 seconds for the initial response. Subsequent steps are fast.
- **`docker: Error response from daemon: pull access denied for scienceworld`**: Re-run the image build step above.
- **Java errors in container logs**: Ensure the Docker image was built with OpenJDK 21. Run `docker run --rm scienceworld:latest java -version` to verify.
- **Need cleanup after interruption**: Run `curl -X DELETE http://localhost:8000/sessions`.

Swagger docs are available at `http://localhost:8000/docs`.
