# Community plugins

Lightweight-Harness supplies one shell tool (`run_command`) and an in-process conversation by default. No plugin,
prompt, memory file, skill, or context policy is loaded implicitly. The following
small Python API is experimental; community distribution and compatibility
conventions are still planned.

## Loading

Install your package into the same Python environment as Lightweight-Harness, then opt in:

```toml
[plugins]
# 같은 Python 환경에 설치된 진입점만 명시하며, 이 순서대로 setup을 실행한다.
enabled = ["my_package:setup", "another_package:setup"]
```

Or use `lightweight-harness --plugin my_package:setup`. Config entries run first, followed by CLI
entries, with duplicate strings removed. `lightweight-harness --no-plugins` disables both. There
is no package discovery, repository scan, dependency installer, or plugin registry
in the core. Missing modules and setup failures are visible errors; a failed
provider switch keeps the existing session.

Each entry names an importable module and a callable accepting one `Agent`:

```python
def setup(agent):
    # 새 세션에서 한 번 실행된다. 모델에 보낼 스키마와 로컬 실행 함수를 함께 등록한다.
    agent.add_tool(
        {
            "type": "function",
            "function": {
                "name": "echo",
                "description": "Return the supplied text.",
                # 모델이 text 문자열 하나를 인자로 보내도록 호출 형식을 설명한다.
                "parameters": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                    "additionalProperties": False,
                },
            },
        },
        # 모델이 보낸 text를 키워드 인자로 받아 도구 결과 문자열로 반환한다.
        lambda text: text,
    )
```

Handlers receive keyword arguments and must return a string. Exceptions are
returned to the model as tool errors. Tool names must be unique; the built-in
`run_command` cannot be accidentally replaced through `add_tool`.

## Context and events

| Surface | Purpose |
| --- | --- |
| `agent.messages` | Mutable session history, initially empty |
| `agent.before_request` | List of `callback(agent)` functions, run before every model request |
| `agent.event_handlers` | List of `callback(event)` functions |
| `agent.add_tool(definition, handler)` | Register an extra model-visible tool |
| `agent.provider` | Selected provider configuration |
| `agent.tools` | This session's tool schemas |

Events have `kind`, `text`, and `tool` attributes. Kinds are `assistant`,
`tool_start`, `tool_end`, and `turn_end`. The last event fires after a final model
response without tool calls; it is not emitted after a transport failure.
Completed tool results have already been appended when `tool_end` fires.

Setup runs once per new session. Requests, tool handlers, and event handlers run
synchronously on the agent worker. Hooks execute in registration order. Errors
in context/event hooks surface to the UI; the core does not retry or suppress
them. Keep setup fast and do not update Textual widgets from a worker callback.

A memory plugin can load history during setup and save it on `turn_end`. A skill
plugin can explicitly add context in `before_request`. A compression plugin can
replace completed turns there. Preserve every assistant tool call and its matching
tool result as a unit; never split pending calls from their results. These policies
belong to the selected plugins and are not supplied by the core.

History uses OpenAI-style `user`, `assistant`, and `tool` messages. A plugin may
explicitly add `system` or `developer` messages. For Anthropic, these become the
top-level `system` field; the field is omitted when there are none. Native
Anthropic assistant blocks are retained in `_anthropic_content`, including opaque
thinking signatures. Preserve this metadata when saving/restoring history, and
edit the native blocks too if rewriting an Anthropic assistant message. Tool
results use `_is_error` internally; private fields are stripped from OpenAI wire
messages. Switching providers starts a new session so native histories are not
silently sent to a different backend.

`/clear` and `/use` create a new Agent and rerun enabled plugins. A memory plugin
may therefore restore its own saved state even after `/clear`; its reset policy
must be documented by that plugin. There is currently no plugin teardown hook.
Avoid retaining long-lived external resources that require one.

## Runnable example

From a source checkout with Lightweight-Harness installed:

```bash
# 예제 모듈을 import할 경로를 이번 실행에만 추가하고 로그 플러그인을 명시적으로 선택한다.
PYTHONPATH="$PWD/examples/plugins" lightweight-harness --plugin session_log:setup
```

The bundled [session logger](../examples/plugins/session_log.py) writes the entire
conversation as one JSON record per completed turn to `lightweight-harness-session.jsonl` in the
working directory. It does not restore history or add a prompt/tool. It is never
loaded automatically. Logs include user content and tool outputs, so enable this
only when you want those recorded.

Plugins execute ordinary Python with the same filesystem, environment, network,
and shell access as Lightweight-Harness. Docker is recommended for both the bare CLI and any
selected plugins.
