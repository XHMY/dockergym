# DockerGym

Wrap Dockerized gym-like environments behind a REST API.

DockerGym manages container lifecycle, session state, request batching, and worker I/O so you can focus on environment logic.

## Documentation Map

- Want a working demo quickly: follow **Quick Start: Run ALFWorld** below.
- Need ALFWorld-specific details: see [`dockergym/envs/alfworld/README.md`](dockergym/envs/alfworld/README.md).
- Building your own environment: see **Implement a custom environment** in this file.

## Quick Start: Run ALFWorld

This is the fastest path to a successful end-to-end run.

### Architecture (ALFWorld)

```
                ┌──────────────────────────┐
Client A ────► │    DockerGym Server       │
Client B ────► │  SessionManager + Batcher │
Client C ────► │       (docker-py)         │
                └──┬────────┬────────┬──────┘
                   │        │        │  stdin/stdout
                ┌──▼──┐  ┌──▼──┐  ┌──▼──┐
                │ C1  │  │ C2  │  │ C3  │  Docker containers
                └─────┘  └─────┘  └─────┘  (alfworld-text)
```

### 1) Install

```bash
git clone https://github.com/XHMY/dockergym.git
cd dockergym
pip install -e .
```

### 2) One-time ALFWorld setup

```bash
# Build the ALFWorld worker image
DOCKERFILE_DIR=$(python -c "import dockergym.envs.alfworld, os; print(os.path.dirname(dockergym.envs.alfworld.__file__))")
docker build -t alfworld-text:latest "$DOCKERFILE_DIR"

# Download ALFWorld data to your host cache
docker run --rm -v ~/.cache/alfworld:/data alfworld-text:latest \
  bash -lc "alfworld-download"
```

### 3) Start the ALFWorld API server

```bash
python -m dockergym.envs.alfworld \
  --data-volume ~/.cache/alfworld:/data:ro \
  --port 8000
```

### 4) Run the bundled ALFWorld example client

Run this in a second terminal:

```bash
python -m dockergym.envs.alfworld.example \
  --base-url http://localhost:8000 \
  --concurrent 8 \
  --total_jobs 20
```

The example creates sessions, runs random admissible actions, prints aggregate results, and cleans up sessions automatically.

### 5) Verify server health

```bash
curl http://localhost:8000/health
```

Swagger docs are available at `http://localhost:8000/docs`.

For full ALFWorld options and troubleshooting, see [`dockergym/envs/alfworld/README.md`](dockergym/envs/alfworld/README.md).

## Implement a custom environment

### Create a worker

The worker runs **inside** the Docker container. Subclass `BaseWorker`:

```python
# my_worker.py
from dockergym import BaseWorker


class MyWorker(BaseWorker):
    def init_env(self, env_id, params):
        # Set up your environment
        return observation, 0.0, False, {"extra_key": "value"}

    def step_env(self, action):
        # Execute action, return results
        return observation, reward, done, {"extra_key": "value"}


if __name__ == "__main__":
    MyWorker().run()
```

### Run the server

```bash
python -m dockergym \
  --docker-image my-env:latest \
  --worker-command python -u /app/my_worker.py \
  --volume ./data:/data:ro \
  --max-sessions 64 \
  --port 8000
```

Or programmatically with hooks:

```python
from dockergym import Hooks, ServerConfig, create_app


class MyHooks(Hooks):
    async def on_startup(self, app):
        # Discover environments, populate config, etc.
        pass

    async def on_create_session(self, env_id, params):
        # Customize session creation
        return {"env_id": env_id or "default", **params}


config = ServerConfig(
    docker_image="my-env:latest",
    worker_command=["python", "-u", "/app/my_worker.py"],
    volumes=["./data:/data:ro"],
    env_files=["env1", "env2"],
)
app = create_app(config, hooks=MyHooks())
```

## API Endpoints

| Method   | Path                  | Description                 |
|----------|-----------------------|-----------------------------|
| `POST`   | `/sessions`           | Create a new session        |
| `POST`   | `/sessions/{id}/step` | Execute an action           |
| `GET`    | `/sessions/{id}`      | Get session info            |
| `DELETE` | `/sessions/{id}`      | End a session               |
| `DELETE` | `/sessions`           | End all sessions            |
| `GET`    | `/environments`       | List available environments |
| `GET`    | `/health`             | Server health check         |

### Create Session

```bash
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"env_id": "my-env-1", "params": {"difficulty": "hard"}}'
```

Response:

```json
{
  "session_id": "uuid",
  "env_id": "my-env-1",
  "observation": "You are in a room...",
  "info": {},
  "status": "active",
  "created_at": "...",
  "last_active_at": "..."
}
```

### Step

```bash
curl -X POST http://localhost:8000/sessions/{id}/step \
  -H "Content-Type: application/json" \
  -d '{"action": "go north"}'
```

Response:

```json
{
  "session_id": "uuid",
  "observation": "You see a door...",
  "reward": 1.0,
  "done": false,
  "info": {
    "admissible_commands": ["go east", "look"]
  }
}
```

## Worker protocol

Communication between the server and worker containers uses JSON lines over stdin/stdout.

```
INIT:  -> {"cmd": "init", "env_id": "...", ...extra_params}
       <- {"status": "ok", "observation": "...", "reward": 0.0, "done": false, ...extras}

STEP:  -> {"cmd": "step", "action": "..."}
       <- {"status": "ok", "observation": "...", "reward": <float>, "done": <bool>, ...extras}

ERROR: <- {"status": "error", "message": "..."}
```

- Workers **must** redirect stdout to stderr before processing to prevent log pollution.
- Workers **must** flush stdout after each response.
- `observation` (str), `reward` (float), and `done` (bool) are required in OK responses.
- Extra keys are passed through to the API `info` dict.
- The server accepts `score` as an alias for `reward` (backward compatibility).

## Configuration

`ServerConfig` fields:

| Field                     | Type            | Default                | Description                         |
|---------------------------|-----------------|------------------------|-------------------------------------|
| `docker_image`            | `str`           | *(required)*           | Docker image for workers            |
| `worker_command`          | `List[str]`     | *(required)*           | Command to run inside containers    |
| `volumes`                 | `List[str]`     | `[]`                   | Volume mounts (host:container:mode) |
| `env_files`               | `List[str]`     | `[]`                   | Available environment IDs           |
| `container_label`         | `str`           | `"dockergym-session"`  | Docker label for tracking           |
| `container_env`           | `Dict[str,str]` | `{}`                   | Env vars for containers             |
| `max_sessions`            | `int`           | `64`                   | Max concurrent sessions             |
| `container_stop_timeout_s`| `int`           | `2`                    | Docker stop timeout                 |
| `batch_window_ms`         | `int`           | `50`                   | Request batching window             |
| `idle_timeout_s`          | `int`           | `120`                  | Session idle timeout                |
| `command_timeout_s`       | `float`         | `60.0`                 | Worker command timeout              |
| `host`                    | `str`           | `"0.0.0.0"`            | Bind address                        |
| `port`                    | `int`           | `8000`                 | Listen port                         |
| `title`                   | `str`           | `"DockerGym API"`      | API title                           |
| `version`                 | `str`           | `"0.1.0"`              | API version                         |
