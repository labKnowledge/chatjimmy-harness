# Install

## Prerequisites

- Python 3.10+
- Network access to `https://chatjimmy.ai` (no API key)

### Install `uv` (recommended)

This project uses [uv](https://docs.astral.sh/uv/) to create the tool env and put scripts on your PATH. You only need it for install/update — not to *run* `chatjimmy` afterward.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
# persist for bash:
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

Without `uv`, use a venv + pip (see [Alternative: pip](#alternative-pip)).

## User-wide install (recommended)

From the repo root:

```bash
cd /path/to/chatjimmy-harness
uv tool install -e .
```

That installs into `~/.local/share/uv/tools/chatjimmy-harness/` and links:

| Command | Path |
|---------|------|
| `chatjimmy` | `~/.local/bin/chatjimmy` |
| `cj` | `~/.local/bin/cj` |
| `cjh` | `~/.local/bin/cjh` |

Verify:

```bash
which chatjimmy cj
cj doctor
cj -p "hi"
# cj   # opens interactive agent
```

If `command not found`, ensure `~/.local/bin` is on `PATH` (see above), then open a new terminal or `source ~/.bashrc`.

The `-e` (editable) flag means code edits under this repo are picked up on the next run without reinstalling. After changing `pyproject.toml` entry points or dependencies, re-run:

```bash
uv tool install --force -e .
```

## Dev / local venv only

Keeps everything inside the project `.venv` (use `uv run …` or activate first):

```bash
cd /path/to/chatjimmy-harness
uv sync
uv run chatjimmy health
# or:
source .venv/bin/activate
chatjimmy health
```

## Alternative: pip

```bash
cd /path/to/chatjimmy-harness
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

chatjimmy health
cj ask "hi"
```

To expose commands without activating the venv, install with pip’s user scheme (or symlink `.venv/bin/chatjimmy` into `~/.local/bin`).

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `CHATJIMMY_BASE_URL` | `https://chatjimmy.ai` | API base URL |
| `CHATJIMMY_TIMEOUT` | `60` | HTTP timeout (seconds) |

Same values can be passed as global CLI flags: `--base-url`, `--timeout`.

## Update

```bash
cd /path/to/chatjimmy-harness
git pull   # if using git
uv tool install --force -e .
```

## Uninstall

```bash
uv tool uninstall chatjimmy-harness
# removes ~/.local/bin/{chatjimmy,cj,cjh} and the tool env
```
