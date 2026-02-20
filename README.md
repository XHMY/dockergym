# 🐳 DockerGym

Wrap Dockerized gym-like environments behind a REST API. DockerGym manages container lifecycle, session state, request batching, and worker I/O so you can focus on environment logic.

## Documentation Map

- Want a working demo quickly: follow **Quick Start: Run ALFWorld** below.
- Need ALFWorld-specific details: see [`dockergym/envs/alfworld/README.md`](dockergym/envs/alfworld/README.md).
- Building your own environment: see **Implement a custom environment** in this file.
- Using Claude Code to migrate an environment automatically: see **Add an environment with Claude Code** below.

## Quick Start: Run ALFWorld

This is the fastest path to a successful end-to-end run.

### Architecture (ALFWorld)

```
               ┌───────────────────────────┐
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
# Build the ALFWorld worker image ( This step takes ~834.1s to install all dependencies inside docker)
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


## Add an environment with Claude Code

This repository ships a [Claude Code skill](https://code.claude.com/docs/en/skills) that automates environment migration. Instead of manually creating all the files described above, you can point Claude Code at an existing environment and let it scaffold everything for you.

### Prerequisites

- [Claude Code](https://code.claude.com) installed and configured.
- This repository cloned locally.

### Usage

Open a Claude Code session inside this repository and describe the environment you want to add. The skill activates automatically when Claude detects you're asking to add, migrate, or port an environment. You can also invoke it explicitly:

```
/add-environment
```

**Example prompt:**

```
/add-environment Add the ScienceWorld environment (https://github.com/allenai/ScienceWorld) to this repo.
It's a text-based virtual environment for elementary science tasks, installed via
`pip install scienceworld`. It requires Java 1.8+. Tasks are selected by task name
(e.g. "boil", "melt") and variation index. Each step takes a text action and returns
an observation string, score, and list of valid actions.
```

### What the skill does

Claude reads the target environment's source code, then creates a complete package under `dockergym/envs/<env_name>/` following the same structure as the ALFWorld reference implementation:

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `worker.py` | Adapts the environment's `reset()`/`step()` to the DockerGym worker protocol |
| `app.py` | Host-side hooks for environment discovery and session creation |
| `__main__.py` | CLI entry point with argparse (`python -m dockergym.envs.<env_name>`) |
| `Dockerfile` | Builds a Docker image with the environment and all its dependencies |
| `example.py` | Example client with single-session and concurrent-session demos |
| `README.md` | Build, setup, run, and troubleshooting instructions |

### What you do after

Once Claude finishes, follow the generated `README.md` to build, run, and test. For example, if you added [ScienceWorld](https://github.com/allenai/ScienceWorld):

1. **Build the Docker image:**

```bash
DOCKERFILE_DIR=$(python -c "import dockergym.envs.scienceworld, os; print(os.path.dirname(dockergym.envs.scienceworld.__file__))")
docker build -t scienceworld:latest "$DOCKERFILE_DIR"
```

2. **Start the server:**

```bash
python -m dockergym.envs.scienceworld --port 8000
```

3. **Run the example client:**

```bash
python -m dockergym.envs.scienceworld.example --base-url http://localhost:8000
```

### Skill internals

The skill lives at [`.claude/skills/add-environment/`](.claude/skills/add-environment/) and contains:

- `SKILL.md` — the main instructions Claude follows (8 phases from context gathering through verification).
- `templates/` — skeleton files for every component, derived from the ALFWorld implementation.

You can customize the skill by editing `SKILL.md` or the templates to match your team's conventions.


## Implement a custom environment

### Build a Docker image

> **Prerequisite:** Docker Engine must be installed on your system. See the [official install guide](https://docs.docker.com/engine/install/) for instructions.

The Docker image packages your environment and its dependencies. Inside the image you need the `BaseWorker` class, but you do **not** need the full `dockergym` package — `BaseWorker` is self-contained and relies only on the Python standard library. Copy the single file instead of `pip install`-ing the whole package:

```dockerfile
# Install dockergym BaseWorker (minimal — only stdlib, no extra dependencies)
COPY dockergym/worker.py /app/dockergym/
RUN printf 'from dockergym.worker import BaseWorker\n__all__ = ["BaseWorker"]\n' > /app/dockergym/__init__.py
ENV PYTHONPATH=/app
```

This keeps your image small and avoids pulling in server-side dependencies (FastAPI, docker-py, etc.) that are only needed on the host.

A complete Dockerfile typically looks like this:

```dockerfile
FROM python:3.9-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    git build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dockergym BaseWorker (minimal — only stdlib, no extra dependencies)
COPY dockergym/worker.py /app/dockergym/
RUN printf 'from dockergym.worker import BaseWorker\n__all__ = ["BaseWorker"]\n' > /app/dockergym/__init__.py
ENV PYTHONPATH=/app

# Install your environment's own dependencies
RUN pip install --no-cache-dir <target_package>

COPY dockergym/envs/<env_name>/worker.py /app/worker.py
CMD ["python", "-u", "/app/worker.py"]
```

> **Note:** The build context must be the repo root so `COPY` can reach `dockergym/worker.py`. Build with:
>
> ```bash
> docker build -t my-env:latest -f dockergym/envs/<env_name>/Dockerfile .
> ```

See [`.claude/skills/add-environment/templates/Dockerfile`](.claude/skills/add-environment/templates/Dockerfile) for a full annotated template.

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
