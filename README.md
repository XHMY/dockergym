# DockerGym

Wrap any Docker-containerized gym-like environment into a REST API.

DockerGym handles Docker container lifecycle, session management, request batching, and socket I/O so you can focus on your environment logic.

## Quick Start

### 1. Install

```bash
git clone https://github.com/XHMY/dockergym.git
cd dockergym && pip install -e .
```

### 2. Implement a worker

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

### 3. Run the server

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
from dockergym import create_app, ServerConfig, Hooks

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

| Method   | Path                        | Description                    |
|----------|-----------------------------|--------------------------------|
| `POST`   | `/sessions`                 | Create a new session           |
| `POST`   | `/sessions/{id}/step`       | Execute an action              |
| `GET`    | `/sessions/{id}`            | Get session info               |
| `DELETE` | `/sessions/{id}`            | End a session                  |
| `DELETE` | `/sessions`                 | End all sessions               |
| `GET`    | `/environments`             | List available environments    |
| `GET`    | `/health`                   | Server health check            |

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
  "info": {"admissible_commands": ["go east", "look"]}
}
```

## Worker Protocol

Communication between the server and worker containers uses JSON lines over stdin/stdout.

```
INIT:  → {"cmd": "init", "env_id": "...", ...extra_params}
       ← {"status": "ok", "observation": "...", "reward": 0.0, "done": false, ...extras}

STEP:  → {"cmd": "step", "action": "..."}
       ← {"status": "ok", "observation": "...", "reward": <float>, "done": <bool>, ...extras}

ERROR: ← {"status": "error", "message": "..."}
```

- Workers **must** redirect stdout to stderr before processing to prevent log pollution
- Workers **must** flush stdout after each response
- `observation` (str), `reward` (float), `done` (bool) are required in OK responses
- Extra keys are passed through to the API's `info` dict
- The server accepts `score` as an alias for `reward` (backward compatibility)

## Predefined Environments

DockerGym ships with ready-to-use environment packages. Install the extras you need:

### ALFWorld

Interactive TextWorld environments for household tasks.

```bash
pip install dockergym[alfworld]

# Build the Docker image
DOCKERFILE_DIR=$(python -c "import dockergym.envs.alfworld; import os; print(os.path.dirname(dockergym.envs.alfworld.__file__))")
docker build -t alfworld-text:latest "$DOCKERFILE_DIR"

# Start the server
python -m dockergym.envs.alfworld --data-volume ~/.cache/alfworld:/data:ro
```

See [`dockergym/envs/alfworld/README.md`](dockergym/envs/alfworld/README.md) for full documentation.

## Configuration

`ServerConfig` fields:

| Field                    | Type            | Default               | Description                          |
|--------------------------|-----------------|----------------------|--------------------------------------|
| `docker_image`           | `str`           | *(required)*         | Docker image for workers             |
| `worker_command`         | `List[str]`     | *(required)*         | Command to run inside containers     |
| `volumes`                | `List[str]`     | `[]`                 | Volume mounts (host:container:mode)  |
| `env_files`              | `List[str]`     | `[]`                 | Available environment IDs            |
| `container_label`        | `str`           | `"dockergym-session"`| Docker label for tracking            |
| `container_env`          | `Dict[str,str]` | `{}`                 | Env vars for containers              |
| `max_sessions`           | `int`           | `64`                 | Max concurrent sessions              |
| `container_stop_timeout_s`| `int`          | `2`                  | Docker stop timeout                  |
| `batch_window_ms`        | `int`           | `50`                 | Request batching window              |
| `idle_timeout_s`         | `int`           | `120`                | Session idle timeout                 |
| `command_timeout_s`      | `float`         | `60.0`               | Worker command timeout               |
| `host`                   | `str`           | `"0.0.0.0"`         | Bind address                         |
| `port`                   | `int`           | `8000`               | Listen port                          |
| `title`                  | `str`           | `"DockerGym API"`    | API title                            |
| `version`                | `str`           | `"0.1.0"`           | API version                          |
