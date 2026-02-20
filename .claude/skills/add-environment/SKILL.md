---
name: add-environment
description: Migrate and adapt a user-provided gym-like environment into the DockerGym repository. Use when the user asks to add a new environment, integrate an existing environment, port an environment to DockerGym, or create a new env package under dockergym/envs/.
---

# Add Environment to DockerGym

You are migrating a user-provided environment into the DockerGym framework. Follow every step below carefully. The reference implementation is `dockergym/envs/alfworld/` — study it if anything is unclear.

## Phase 0: Gather Context

Before writing any code, collect the following from the user and/or from the target codebase:

1. **Environment name** — a short snake_case identifier (e.g. `alfworld`, `webshop`, `babyai`). This becomes the package directory name under `dockergym/envs/<env_name>/`.
2. **Source codebase / repo** — where to find the environment. The user may provide a GitHub URL, a local path, or describe the environment in words.
3. **Python dependencies** — packages needed to run the environment inside the container.
4. **System dependencies** — any non-Python packages (apt, build tools, etc.).
5. **Data requirements** — does the environment need external data files? How are they obtained? Where should they live on the host and inside the container?
6. **Init parameters** — what does the environment need to start an episode? (e.g. a game file path, a level ID, a seed, difficulty settings)
7. **Step interface** — what does a single action look like? What comes back? (observation type, reward semantics, done conditions, extra info fields)
8. **Episode lifecycle** — any special reset, cleanup, or resource management?
9. **Environment listing** — how to discover/enumerate available environment instances (e.g. scanning a data directory, reading a config file, a fixed list of IDs).

If the user points to a codebase, read the relevant source files to extract this information yourself. Ask clarifying questions only when genuinely ambiguous.

## Phase 1: Create the Package Directory

Create the directory `dockergym/envs/<env_name>/` with these files:

```
dockergym/envs/<env_name>/
├── __init__.py
├── __main__.py      # CLI entry point
├── app.py           # Hooks subclass + app factory
├── worker.py        # Worker that runs inside Docker
├── Dockerfile       # Docker image build
├── example.py       # Example client script
└── README.md        # Environment-specific docs
```

Create an empty `__init__.py`.

## Phase 2: Implement `worker.py`

The worker runs **inside** the Docker container. It communicates with the host via the JSON-lines stdin/stdout protocol.

### Option A: Subclass `BaseWorker` (preferred)

Use this when the target environment's Python package can be imported inside the container.

Read the template at [templates/worker_base.py](templates/worker_base.py) for the skeleton. Key rules:

- Import the target environment's libraries at the top of the file.
- `init_env(self, env_id, params)` must return `(observation: str, reward: float, done: bool, info: dict)`.
  - `env_id` is the environment instance identifier (e.g. a game file path, a level name).
  - `params` is a dict of extra parameters from the create-session request.
  - Store the env instance on `self` so `step_env` can use it.
  - The `info` dict's keys are spread flat into the JSON response and become the `info` field in the API response.
- `step_env(self, action)` must return the same 4-tuple.
  - `action` is always a string.
- `close_env(self)` — optional cleanup (close env, release resources).
- The `BaseWorker.run()` method handles stdin/stdout redirection, JSON parsing, and the main loop automatically.
- The `if __name__ == "__main__"` block should just call `MyWorker().run()`.

### Option B: Custom protocol (for complex cases)

Use this only when the environment needs custom stdin/stdout handling (e.g. ALFWorld uses this because it needs to redirect stdout at specific points due to TextWorld's logging behavior).

Read the template at [templates/worker_custom.py](templates/worker_custom.py) for the skeleton. Key rules:

- Redirect `sys.stdout` to `sys.stderr` immediately, keep a reference to the real stdout.
- Read lines from `sys.stdin` in a loop.
- Parse each line as JSON, dispatch on `cmd.get("cmd")`.
- For `"init"`: set up the environment, respond with `{"status": "ok", "observation": ..., ...}`.
- For `"step"`: execute the action, respond with `{"status": "ok", "observation": ..., "reward": ..., "done": ..., ...}`.
- On errors: respond with `{"status": "error", "message": ...}`.
- Always flush stdout after each response.
- Clean up on stdin close.

### Adapting the target environment

When reading the target environment's source:

1. Find the `reset()` or equivalent method — this maps to `init_env`.
2. Find the `step(action)` method — this maps to `step_env`.
3. Identify what observation format is returned. If it's not a string, convert it (e.g. `str(obs)`, `json.dumps(obs)`, or describe the observation).
4. Identify the reward signal and done condition.
5. Identify any extra info fields that would be useful for the API consumer (e.g. `admissible_commands`, `inventory`, `score`, `won`, `goal`).
6. Handle any environment-specific initialization (seeds, configs, data loading).

## Phase 3: Implement `app.py`

This module defines the host-side hooks and the app factory function. Read [templates/app.py](templates/app.py) for the skeleton.

### Hooks subclass

Create a class that inherits from `dockergym.app.Hooks`:

- **`__init__(self, ...)`** — accept the `ServerConfig` and any env-specific config needed to discover environments.
- **`on_startup(self, app)`** — called after core infra is ready. Use this to:
  - Discover available environment instances (scan data dirs, read config, etc.).
  - Populate `self.server_config.env_files` with the list of environment IDs.
  - Store any extra state on `app.state` if needed.
- **`on_create_session(self, env_id, params)`** — called for each new session. Must return a dict with at least `"env_id"`. This dict is sent as the init payload to the worker. Use this to:
  - Pick a random env if `env_id is None`.
  - Filter environments by params (e.g. task type, difficulty).
  - Translate host paths to container paths using `self.server_config.translate_path()`.
  - Add any extra keys the worker needs (e.g. `"game_file"`, `"config"`, `"seed"`).

### App factory

Create a `create_<env_name>_app(server_config, ...)` function that:
1. Instantiates the hooks.
2. Calls `create_app(server_config, hooks=hooks)` from `dockergym.app`.
3. Returns the FastAPI app.

## Phase 4: Implement `__main__.py`

This is the CLI entry point (`python -m dockergym.envs.<env_name>`). Read [templates/__main__.py](templates/__main__.py) for the skeleton.

Must include:

1. `argparse` argument parser with at least:
   - `--docker-image` (default: `<env_name>:latest`)
   - `--max-sessions` (default: 64)
   - `--host` (default: `0.0.0.0`)
   - `--port` (default: 8000)
   - `--idle-timeout`
   - `--batch-window-ms`
   - Any env-specific args (e.g. `--data-volume`, `--config`, `--difficulty`)
2. Resolve `env_package_dir` as `os.path.dirname(os.path.abspath(__file__))`.
3. Build the volumes list:
   - Mount the package directory into the container so the worker script is accessible: `f"{env_package_dir}:/app/<env_name>_env:ro"`.
   - Mount any data volumes the user specifies.
4. Construct `ServerConfig` with all fields.
5. Call the app factory and run with `uvicorn.run(app, ...)`.

## Phase 5: Write the `Dockerfile`

Read [templates/Dockerfile](templates/Dockerfile) for the skeleton.

Rules:
- Use an appropriate Python base image (e.g. `python:3.9-slim`, `python:3.11-slim`).
- Install system dependencies with `apt-get` if needed.
- Install Python dependencies with `pip`.
- **Install the target environment package** — this is the critical step. Use `pip install` for PyPI packages or `pip install "pkg @ git+https://..."` for GitHub repos.
- Set any required environment variables (e.g. data paths).
- Create necessary directories.
- The `CMD` should be a simple verification command (the actual worker command is set by `ServerConfig.worker_command` and overrides CMD at runtime).
- Keep the image as small as possible (use `--no-cache-dir`, clean up apt lists).

## Phase 6: Write `example.py`

Read [templates/example.py](templates/example.py) for the skeleton.

The example script should demonstrate:
1. A `Session` context manager that creates a session on enter and deletes on exit.
2. A single-session demo that creates one episode, runs a few steps (random or scripted), and prints results.
3. A concurrent-sessions demo using `joblib.Parallel` that stress-tests the server.
4. Proper error handling and health-check verification.
5. Use `requests` for HTTP and `argparse` for CLI options.

## Phase 7: Write `README.md`

The README must cover:

1. **Title and one-line description** of the environment.
2. **What runs where** (API server on host, worker in container, data mounted).
3. **First successful run** — step-by-step instructions:
   - Build the Docker image (with the exact command).
   - Download/prepare any required data.
   - Start the API server.
   - Verify with health check.
   - Run the example client.
4. **Environment-specific session behavior** (what params are accepted, what info fields are returned).
5. **CLI options** with a full example command.
6. **Troubleshooting** common issues.
7. Link to root README for shared API docs and worker protocol.

For the Docker image build command, always use this pattern (repo root as context so the Dockerfile can COPY dockergym):
```bash
REPO_ROOT=$(python -c "import dockergym, os; print(os.path.dirname(os.path.dirname(dockergym.__file__)))")
docker build -t <env_name>:latest -f "$REPO_ROOT/dockergym/envs/<env_name>/Dockerfile" "$REPO_ROOT"
```

## Phase 8: Verification Checklist

Before declaring the migration complete, verify:

- [ ] `dockergym/envs/<env_name>/__init__.py` exists (can be empty).
- [ ] `worker.py` implements the JSON-lines protocol correctly (init + step).
- [ ] `worker.py` returns `observation` (str), `reward` (float), `done` (bool) in every OK response.
- [ ] `worker.py` redirects stdout to stderr before processing.
- [ ] `app.py` subclasses `Hooks` and implements `on_startup` and `on_create_session`.
- [ ] `app.py` has a `create_<env_name>_app()` factory function.
- [ ] `__main__.py` builds `ServerConfig` correctly with all volumes and worker command.
- [ ] `__main__.py` mounts the package dir into the container for worker access.
- [ ] `Dockerfile` installs the target environment and all dependencies.
- [ ] `Dockerfile` uses a slim base image and cleans up after apt-get.
- [ ] `example.py` demonstrates single and concurrent session usage.
- [ ] `README.md` has build, setup, run, and troubleshoot instructions.
- [ ] The worker command in `ServerConfig` matches the container path: `["python", "-u", "/app/<env_name>_env/worker.py"]`.
- [ ] Volume mounts use the right paths and modes (`:ro` for read-only data).
- [ ] The `container_label` is set to `"<env_name>-session"` for easy identification.
- [ ] Path translation works if host paths differ from container paths.

## Important Patterns

### Path translation

When the host discovers environment files by scanning a host path (e.g. `~/.cache/myenv/levels/`), but the container sees them at a different mount point (e.g. `/data/levels/`), use `config.translate_path(host_path)` in `on_create_session` to map the path for the worker.

### Environment variables in the container

Use `ServerConfig.container_env` to pass environment variables to the worker container, or set them in the Dockerfile with `ENV`.

### Reading environment configuration from user's codebase

When migrating an existing environment, look for:
- `gym.Env` subclasses — the `reset()` and `step()` methods define the interface.
- Configuration files (YAML, JSON, TOML) — they define data paths and settings.
- `setup.py` / `pyproject.toml` / `requirements.txt` — they list dependencies.
- Dockerfile or docker-compose if the project already has one — reuse what you can.
- Example scripts or notebooks — they show how the environment is typically used.
