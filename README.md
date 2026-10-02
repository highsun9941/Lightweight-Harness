# Lightweight-Harness

[![English](https://img.shields.io/badge/English-0969DA?style=for-the-badge)](README.md) [![한국어](https://img.shields.io/badge/%ED%95%9C%EA%B5%AD%EC%96%B4-555555?style=for-the-badge)](README.ko.md)

> **The model decides. The runtime executes.**

As LLMs become more capable, we believe the harness around them should become lighter. Layering excessive system prompts and fixed workflows on top of the instructions and tool-use capabilities already supplied by models and API providers can interfere with the model's judgment and reduce its effectiveness.

Lightweight-Harness exposes **one shell tool, `run_command`, by default**. The model uses shell commands to read, search, and edit files, and to run tests. The runtime passes along user input, the current session's conversation, and tool results without automatically injecting its own system prompt or repository instructions. Planning, execution order, diagnosis, and retries are left to the model.

Like CC Switch, Lightweight-Harness lets you configure multiple API providers as profiles and switch between them. We aim to build an ecosystem where users can assemble only the features they want—harnesses, long-term memory, context compression, skills, and additional tools—from community plugins. For now, the project provides a small plugin entry point, with no plugins enabled by default.

**There are no built-in safety guardrails. We recommend running Lightweight-Harness in Docker.** File changes and shell commands run with the process's permissions, without a separate approval step.

## Installation

Install on Linux, macOS, or WSL with one command:

```bash
# Use this repository's installer to prepare an isolated Python environment and the lightweight-harness command.
curl -fsSL https://raw.githubusercontent.com/highsun9941/Lightweight-Harness/main/install.sh | bash
```

The installer prepares [uv](https://docs.astral.sh/uv/) and Python 3.12 if needed, then installs this repository's `main` branch in an isolated Python environment. You do not need Python or Git preinstalled, and the installer does not use `sudo`. Run `lightweight-harness` after installation. If `~/.local/bin` is not on your PATH, follow the instructions printed by the installer.

```bash
# Make commands installed in your user directory available to the current shell.
export PATH="$HOME/.local/bin:$PATH"
lightweight-harness
```

Run the same install command again to update. The default installation directory is `~/.local/share/lightweight-harness`, and the executable is `~/.local/bin/lightweight-harness`. The installer does not automatically change provider settings or shell profiles. If it conflicts with an unrelated existing `lightweight-harness` command, installation stops with an explanation.

To inspect the script first or install a particular tag or commit:

```bash
# Download the script to review its behavior and supported options before installing.
curl -fsSL https://raw.githubusercontent.com/highsun9941/Lightweight-Harness/main/install.sh -o install.sh
less install.sh
bash install.sh --help
# Replace main with the Git ref you want to install.
bash install.sh --ref main
```

Set `LIGHTWEIGHT_HARNESS_INSTALL_DIR` to choose the installation directory and `LIGHTWEIGHT_HARNESS_BIN_DIR` to choose the executable directory. Both must be absolute paths; use the same values when reinstalling. You can also select a Git ref with `LIGHTWEIGHT_HARNESS_REF`. When piping the script, pass environment variables to `bash`:

```bash
# Set the ref for bash on the receiving side of the pipe.
curl -fsSL https://raw.githubusercontent.com/highsun9941/Lightweight-Harness/main/install.sh | LIGHTWEIGHT_HARNESS_REF=main bash
```

If you already have Python 3.12 or later and pipx, you can install directly:

```bash
# Install this repository's source in pipx's isolated environment.
pipx install 'git+https://github.com/highsun9941/Lightweight-Harness.git'
```

For development, install from a source checkout:

```bash
# Prepare a development environment that uses your local source changes.
git clone https://github.com/highsun9941/Lightweight-Harness.git
cd Lightweight-Harness
# Isolate dependencies from system Python and use an editable install.
python -m venv .venv
source .venv/bin/activate
pip install -e .
lightweight-harness
```

The directory you launch Lightweight-Harness from is its working directory. In a source installation, `python -m lightweight_harness` starts the same UI.

When updating an existing installation, reinstall and place your provider configuration in `~/.config/lightweight-harness/config.toml`, or select its current location with `--config`. Project-specific environment variables now use the `LIGHTWEIGHT_HARNESS_` prefix.

## Core behavior

By default, model requests contain the user conversation, previous model responses, tool results, and a single tool: `run_command`.

| Tool | Behavior |
| --- | --- |
| `run_command` | Execute a shell command and return its exit code and output |

The model uses this tool for file reads, searches, edits, program execution, and tests. There are no separate built-in file tools.

The runtime repeats the model response, tool execution, and result delivery cycle until the model responds without tool calls. Shell commands start in the current working directory, but file access is not restricted to that directory.

- No system or developer prompt is added by the core.
- `AGENTS.md`, memory, skills, and repository maps are not loaded automatically. The model can read them through shell commands when needed.
- There is no automatic planning, model routing, hidden retry policy, or context summarization/compression.
- Conversation history stays in the current process. By default, it is neither saved nor restored on the next launch.
- Context-limit and API errors are surfaced directly. Tool execution errors are returned to the model, which decides what to do next.
- The UI shortens long tool output for display, while the model receives the full tool result.

## API provider profiles

Define profiles in `~/.config/lightweight-harness/config.toml`. Use `--config` or `LIGHTWEIGHT_HARNESS_CONFIG` to select a different file.

```toml
# Use this profile when neither the CLI nor environment variables select another provider.
default_provider = "openrouter"

[plugins]
# Use only the core by default. Add optional extensions explicitly as module:setup entries.
enabled = []

[providers.openrouter]
# name is displayed in the UI; the transport adds the API path to base_url.
name = "OpenRouter"
base_url = "https://openrouter.ai/api/v1"
# Read the key from this environment variable at request time instead of storing it here.
api_key_env = "OPENROUTER_API_KEY"
model = "openai/gpt-5"

[providers.deepseek]
# Reuse the OpenAI-compatible transport with a different endpoint and model.
name = "DeepSeek"
base_url = "https://api.deepseek.com/v1"
api_key_env = "DEEPSEEK_API_KEY"
model = "deepseek-chat"

[providers.anthropic]
# Convert requests and responses to and from the Anthropic Messages format.
name = "Anthropic"
api_format = "anthropic"
base_url = "https://api.anthropic.com/v1"
api_key_env = "ANTHROPIC_API_KEY"
model = "your-claude-model" # Replace with a model ID available to your account.
max_tokens = 4096 # Maximum output tokens per response.

[providers.local]
name = "Local"
base_url = "http://localhost:1234/v1"
api_key_env = "" # Use only for a local server that does not require authentication.
model = "your-local-model" # Replace with the model ID loaded on your server.
```

The default `api_format = "openai"` connects to servers that support the OpenAI-compatible **Chat Completions** API and tool calling. Use `anthropic` for the native **Messages** API. Set `base_url` to the API root; the runtime appends `/chat/completions` or `/messages`, respectively. `max_tokens` sets the maximum output tokens for Anthropic requests.

```bash
# Set the key referenced by the profile, then select a provider.
export OPENROUTER_API_KEY=...
lightweight-harness --provider openrouter
# Override the config file and model for this run only.
lightweight-harness --config /path/to/config.toml --provider anthropic --model YOUR_MODEL_ID
```

Provider selection follows this order: `--provider` → `LIGHTWEIGHT_HARNESS_PROVIDER` → `default_provider` → the first profile by name in alphabetical order. Model selection follows `--model` → `LIGHTWEIGHT_HARNESS_MODEL` → the profile's `model`. API keys are read from the environment variable named by `api_key_env`.

Environment-variable shortcuts are also supported. `OPENAI_API_KEY` or `LIGHTWEIGHT_HARNESS_API_KEY` creates an `openai` profile, and `OPENROUTER_API_KEY` creates an `openrouter` profile. `OPENAI_BASE_URL` overrides the default OpenAI-compatible endpoint. A TOML profile with the same name overrides the corresponding shortcut profile.

UI commands:

| Command | Behavior |
| --- | --- |
| `/help` | Show help |
| `/providers` or `/models` | List configured providers and models |
| `/use <provider> [model]` | Select a provider and start a new session |
| `/plugins` | List currently active plugins |
| `/clear` | Start a new session with the current provider |
| `/quit` | Exit |

Switching providers does not transfer the previous conversation to the new provider. `/use` applies to the current run; set the default for future runs in the config file. New requests and session changes are blocked while a task is running. `/quit` does not terminate a running shell process.

## Optional plugins

The default plugin list is empty. Install a plugin package in the same Python environment, then specify its `setup(agent)` entry point:

```toml
[plugins]
# Call the installed module's setup function when a new Agent is initialized.
enabled = ["my_plugin:setup"]
```

```bash
# Append one plugin to the configured list.
lightweight-harness --plugin my_plugin:setup
# In a separate run, disable all plugins selected through config or CLI options.
lightweight-harness --no-plugins
```

Entries from `--plugin` are appended after the configured list, in order. Duplicate entry points run only once. `--no-plugins` ignores both lists. Plugins are not discovered or installed automatically.

Plugins can register additional tools, process conversation history before requests, and subscribe to events to implement harnesses, memory, compression, or skill loading. Explicitly selected plugins can change the default tool list and prompts. Plugins are Python code running with the same permissions as the CLI.

See the [plugin authoring guide](docs/plugins.md) and [session logging example](examples/plugins/session_log.py). Community package listings, distribution and installation tools, and version compatibility conventions are areas for future development.

## Running in Docker

```bash
# Build an image containing Python, Git, ripgrep, and the CLI.
docker build -t lightweight-harness .
# Match host file ownership and pass in the working directory and required environment variables.
docker run --rm -it \
  --user "$(id -u):$(id -g)" \
  --cap-drop ALL --security-opt no-new-privileges \
  -v "$PWD:/workspace" \
  -e OPENROUTER_API_KEY \
  -e LIGHTWEIGHT_HARNESS_PROVIDER=openrouter \
  -e LIGHTWEIGHT_HARNESS_MODEL=openai/gpt-5 \
  lightweight-harness
```

On Linux, passing your host UID/GID with `--user` aligns file permissions for the mounted working directory. The image includes Python, Git, and ripgrep. Add any other runtimes your project needs to the image.

To use a config file and a custom provider:

```bash
# Mount the config file read-only and tell the CLI where to find it inside the container.
docker run --rm -it \
  --user "$(id -u):$(id -g)" \
  --cap-drop ALL --security-opt no-new-privileges \
  -v "$PWD:/workspace" \
  -v "$HOME/.config/lightweight-harness/config.toml:/tmp/lightweight-harness-config.toml:ro" \
  -e LIGHTWEIGHT_HARNESS_CONFIG=/tmp/lightweight-harness-config.toml \
  -e ANTHROPIC_API_KEY \
  lightweight-harness --provider anthropic
```

Compose uses this repository as the working directory by default:

```bash
# Match host file ownership and rebuild the image from the current source.
LIGHTWEIGHT_HARNESS_UID="$(id -u)" LIGHTWEIGHT_HARNESS_GID="$(id -g)" docker compose run --rm --build lightweight-harness
```

Docker separates the execution environment, but the process can still access writable mounts and any keys passed into it. Mount only the working directory and pass only the keys you need. Inside a container, `localhost` refers to that container. To connect to a model server on the host, use a host address appropriate for your environment.

## Repository structure

These are the files used to run, install, configure, and verify the project, with their roles noted alongside them.

```text
Lightweight-Harness/
├── lightweight_harness/      # CLI runtime core
│   ├── __init__.py           # Package version
│   ├── __main__.py           # Entry point for python -m lightweight_harness
│   ├── app.py                # CLI options, config loading, and UI startup
│   ├── tui.py                # Terminal UI, user commands, and provider/session switching
│   ├── agent.py              # Model request → tool execution → result delivery loop
│   ├── tools.py              # Definition and execution of the sole built-in tool, run_command
│   ├── providers.py          # API provider and model selection from TOML and environment variables
│   ├── transport.py          # OpenAI-compatible and Anthropic request/response conversion
│   └── plugins.py            # Loading of explicitly selected module:setup plugins
├── examples/                 # Configuration and plugin examples for users to opt into
│   ├── config.toml           # API provider profiles and plugin configuration examples
│   └── plugins/
│       └── session_log.py    # Optional plugin that saves completed conversations as JSONL
├── docs/
│   └── plugins.md            # Plugin authoring guide, extension API, and runnable example
├── tests/                    # Automated tests that do not require real API keys
│   ├── conftest.py           # Isolation from personal configuration and credential variables
│   ├── test_agent.py         # Model/tool loop, error results, and plugin selection
│   ├── test_tools.py         # Shell file operations, exit codes/output, and removed tools
│   ├── test_transport.py     # OpenAI/Anthropic requests and tool-call round trips
│   ├── test_providers.py     # Provider configuration, selection precedence, and authentication
│   ├── test_config.py        # CLI options and forwarding of config/plugin selections
│   ├── test_tui.py           # UI provider/session switching and overlapping request handling
│   └── test_installer.py     # Installation, reinstallation, uv bootstrap, and failure handling
├── .github/workflows/
│   └── ci.yml                # Tests and Linux/macOS installation and reinstallation CI
├── install.sh                # curl installer, uv/Python setup, and installation/updates
├── pyproject.toml            # Package metadata, dependencies, and lightweight-harness command registration
├── lightweight_harness.py    # Direct script entry point for python lightweight_harness.py
├── Dockerfile                # Runtime image with Python, Git, and ripgrep
├── docker-compose.yml        # Container configuration for the working directory and environment
├── .dockerignore             # Files excluded from the Docker build context
├── .gitignore                # Local environments, caches, and environment files excluded from Git
├── README.md                 # English guide: project direction, installation, usage, and structure
└── README.ko.md              # Korean guide: project direction, installation, usage, and structure
```

Both `lightweight-harness` and `python -m lightweight_harness` enter through `main()` in `app.py`. `tui.py` passes user input to `agent.py`, which communicates with the model through `transport.py` and executes shell commands through `tools.py`. Configuration and plugins in `examples/` are available for users to select explicitly.

## Development and verification

```bash
# Install test dependencies, then check Python syntax, automated tests, and the CLI entry point.
pip install -e '.[dev]'
python -m compileall -q lightweight_harness
pytest -q
python -m lightweight_harness --help
```

Tests use mock HTTP transports to verify the absence of default prompts, exposure of only `run_command`, tool error results, provider profile selection, OpenAI/Anthropic tool-call round trips, plugin selection, and UI session switching. They also check shell-based file operations and the return of exit codes, standard output, and standard error. No real API calls or API keys are required.

This is an early experimental project. Its direction is to keep the core small and extensions optional.
