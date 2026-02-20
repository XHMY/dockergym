# ALFWorld Environment for DockerGym

A predefined DockerGym environment that wraps [ALFWorld](https://github.com/alfworld/alfworld) TextWorld environments. Each session runs in its own Docker container, communicating via stdin/stdout JSON lines protocol.

## Architecture

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

- One Docker container per session, running `worker.py`
- Auto-batching dispatches concurrent step requests in parallel
- Containers are ephemeral — killed and auto-removed on session end

## Quick Start


### 1. Build the Docker image

```bash
# Find the Dockerfile bundled with the package
DOCKERFILE_DIR=$(python -c "import dockergym.envs.alfworld; import os; print(os.path.dirname(dockergym.envs.alfworld.__file__))")
docker build -t alfworld-text:latest "$DOCKERFILE_DIR"
```

### 2. Download ALFWorld data

```bash
docker run --rm -v ~/.cache/alfworld:/data alfworld-text:latest \
  bash -c "pip install alfworld && alfworld-download"
```

### 3. Start the server

```bash
python -m dockergym.envs.alfworld \
    --data-volume ~/.cache/alfworld:/data:ro \
    --port 8000
```

### 4. Health check

```bash
curl http://localhost:8000/health
```

Swagger docs available at `http://localhost:8000/docs`.

## API Endpoints

| Method   | Path                      | Description                          |
|----------|---------------------------|--------------------------------------|
| `POST`   | `/sessions`               | Create session (start container)     |
| `POST`   | `/sessions/{id}/step`     | Take an action                       |
| `GET`    | `/sessions/{id}`          | Get session status                   |
| `DELETE` | `/sessions`               | Kill all sessions                    |
| `DELETE` | `/sessions/{id}`          | End session (kill container)         |
| `GET`    | `/environments`           | List available game files            |
| `GET`    | `/health`                 | Health check                         |

## CLI Options

```
python -m dockergym.envs.alfworld \
    --config base_config.yaml \
    --docker-image alfworld-text:latest \
    --data-volume ~/.cache/alfworld:/data:ro \
    --max-sessions 8 \
    --batch-window-ms 50 \
    --idle-timeout 120 \
    --host 0.0.0.0 \
    --port 8000
```

## Example Usage

See `example.py` in this package for a full working example including concurrent sessions.

```python
import requests

BASE = "http://localhost:8000"

# Create a session
r = requests.post(f"{BASE}/sessions", json={"params": {"task_type": 1}})
session = r.json()
sid = session["session_id"]
print(session["observation"])
print(session["info"]["admissible_commands"])

# Take actions
r = requests.post(f"{BASE}/sessions/{sid}/step", json={"action": "look"})
result = r.json()
print(result["observation"])
print(result["reward"])
print(result["info"]["admissible_commands"])

# End session
requests.delete(f"{BASE}/sessions/{sid}")

# Kill all sessions (useful for cleanup after crashes)
requests.delete(f"{BASE}/sessions")
```

## Response Schema

### Create Session

```json
{
  "session_id": "uuid",
  "env_id": "/data/json_2.1.1/train/.../game.tw-pddl",
  "observation": "You are in the middle of a room...",
  "info": {
    "admissible_commands": ["go to desk 1", "go to shelf 1", ...],
    "game_file": "/data/json_2.1.1/train/.../game.tw-pddl"
  },
  "status": "active",
  "created_at": "...",
  "last_active_at": "..."
}
```

### Step

```json
{
  "session_id": "uuid",
  "observation": "You arrive at desk 1...",
  "reward": 0.0,
  "done": false,
  "info": {
    "won": false,
    "admissible_commands": ["take pen 1", "go to shelf 1", ...]
  }
}
```

### Kill all sessions via curl

```bash
curl -X DELETE http://localhost:8000/sessions
```
