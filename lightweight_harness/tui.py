# Textual UI는 입력·표시·세션 전환을 맡고, 모델과 도구의 실행은 Agent에 위임한다.
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Footer, Header, Input, Static

from .agent import Agent, AgentEvent
from .providers import ProviderConfig, load_providers, resolve_provider

# 화면·헤더의 바탕색과 역할별 글자색으로 사용자 입력, 모델 응답, 도구 결과, 오류를 구분한다.
# chat은 남는 세로 공간을 채우고 composer는 입력에 필요한 높이만 사용한다.
# status는 한 줄로 유지하며 Input의 기본 테두리는 바깥 composer 테두리와 중복되지 않게 없앤다.
CSS = """
Screen { background: #0b0d10; color: #e6e8eb; }
Header { background: #11151a; color: #e6e8eb; }
#chat { height: 1fr; padding: 1 2; scrollbar-size: 1 1; }
#composer { height: auto; border: round #303842; padding: 0 1; margin: 0 2 1 2; }
#status { height: 1; color: #8f99a6; padding: 0 2; }
.user { color: #9fc3ff; padding: 1 0 0 0; }
.assistant { color: #f0f2f5; padding: 1 0 0 0; }
.tool { color: #8f99a6; padding: 0 0 0 2; }
.error { color: #ff8b8b; }
Input { border: none; background: transparent; }
"""


class LightweightHarnessApp(App[None]):
    # 표시 문구와 스타일은 UI에만 사용되며 모델 프롬프트에는 포함되지 않는다.
    TITLE = "Lightweight-Harness"
    SUB_TITLE = "The model decides. The runtime executes."
    CSS = CSS

    def __init__(
        self,
        provider: ProviderConfig | None = None,
        *,
        config_path: Path | None = None,
        plugins: list[str] | None = None,
    ) -> None:
        # 화면을 만들기 전에 제공자·설정 경로·플러그인 선택과 입력 처리 상태를 보관한다.
        super().__init__()
        self.provider = provider
        # 위젯이 준비된 뒤 세션을 생성해야 초기화 결과를 화면에 표시할 수 있다.
        self.agent: Agent | None = None
        self.config_path = config_path
        self.plugins = list(plugins or [])
        # 동일한 대화 목록을 두 작업이 동시에 수정하지 않도록 UI 진입점에서 관리한다.
        self.busy = False

    def compose(self) -> ComposeResult:
        # 대화 영역을 스크롤 가능하게 하고 상태·입력 영역은 별도 위젯으로 둔다.
        yield Header(show_clock=True)
        yield VerticalScroll(id="chat")
        yield Static(id="status")
        yield Container(Input(placeholder="Describe what you want to change…", id="composer"))
        yield Footer()

    def on_mount(self) -> None:
        # 위젯 생성 후 제공자를 활성화하고, 설정이 없으면 사용자가 설정할 수 있도록 안내한다.
        status = self.query_one("#status", Static)
        if self.provider:
            self._activate(self.provider)
            if self.agent:
                self._add("assistant", "Lightweight-Harness ready. Use /help for commands.")
        else:
            status.update("No provider configured")
            self._add("error", "No provider configured. Add ~/.config/lightweight-harness/config.toml or set an API key environment variable.")
            self._add("assistant", "Run /help for commands.")
        # 실행 권한에 대한 안내일 뿐 실제 명령 승인이나 차단 기능은 아니다.
        self._add("tool", "Shell commands and file writes run without approval. Docker is recommended.")

    def _activate(self, provider: ProviderConfig) -> bool:
        # 새 Agent와 플러그인 초기화에 성공한 뒤에만 이전 세션을 닫는다.
        # 새 설정이 잘못됐을 때 기존 세션을 잃지 않도록 교체 순서를 지킨다.
        try:
            agent = Agent(provider, self._event, plugins=self.plugins)
        except Exception as exc:
            self._add("error", f"{type(exc).__name__}: {exc}")
            return False
        if self.agent:
            self.agent.close()
        self.provider = provider
        # 새 Agent로 교체해 코어가 이전 세션의 대화를 자동으로 넘기지 않도록 한다.
        # 선택한 플러그인은 setup에서 자신의 대화를 복원할 수 있다.
        self.agent = agent
        self.query_one("#status", Static).update(Text(f"{provider.name} · {provider.model} · plugins: {len(agent.plugins)}"))
        return True

    def on_unmount(self) -> None:
        # 작업이 없다면 즉시 연결을 닫는다. 실행 중인 Agent는 작업 스레드의 finally에서 정리한다.
        if self.agent and not self.busy:
            self.agent.close()

    def _add(self, kind: str, text: str) -> None:
        # 모델·도구 출력의 대괄호 등이 Rich 마크업으로 해석되지 않게 일반 Text로 감싼다.
        chat = self.query_one("#chat", VerticalScroll)
        chat.mount(Static(Text(text), classes=kind))
        chat.scroll_end(animate=False)

    def _event(self, event: AgentEvent) -> None:
        # Agent의 작업 스레드가 직접 위젯을 건드리지 않고 UI 스레드로 전달하게 한다.
        if self.is_running:
            self.call_from_thread(self._handle_event, event)

    def _handle_event(self, event: AgentEvent) -> None:
        # 코어의 이벤트를 표시로만 변환한다. 여기서 모델의 다음 행동을 결정하지 않는다.
        if event.kind == "assistant":
            self._add("assistant", event.text)
        elif event.kind == "tool_start":
            self._add("tool", f"↳ {event.tool}")
        elif event.kind == "tool_end":
            # 화면이 긴 출력으로 가득 차는 것을 줄인다. 모델에 전달되는 원본 결과는 자르지 않는다.
            summary = event.text if len(event.text) <= 500 else event.text[:500] + "…"
            self._add("tool", summary)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # 빈 입력은 요청하지 않고, 일반 대화와 UI 명령을 분리한다.
        prompt = event.value.strip()
        if not prompt:
            return
        if self.busy and not prompt.startswith("/"):
            # 처리 중인 요청에 새 대화를 끼워 넣지 않는다. 입력값은 지우기 전이므로 그대로 남는다.
            self._add("error", "A task is still running. Wait before sending another request.")
            return
        event.input.value = ""
        self._add("user", f"> {prompt}")
        if prompt.startswith("/"):
            # 슬래시 명령은 로컬 UI가 처리하며 모델 API에 보내지 않는다.
            self._command(prompt)
            return
        if not self.agent:
            self._add("error", "No provider configured.")
            return
        # 스레드 시작 전에 잠가 빠르게 연속 입력해도 중복 작업이 시작되지 않게 한다.
        self.busy = True
        self.run_agent(self.agent, prompt)

    def _command(self, prompt: str) -> None:
        # 첫 공백으로 명령과 인자를 나누는 작은 명령 집합만 지원한다.
        command, _, arg = prompt.partition(" ")
        if self.busy and command in {"/use", "/clear"}:
            # 실행 중인 Agent가 쓰는 대화·연결을 도중에 교체하지 않는다.
            self._add("error", "A task is still running. Wait before changing the session.")
            return
        if command in {"/q", "/quit", "/exit"}:
            # UI를 종료한다. 실행 중인 셸 자식 프로세스를 종료시키는 명령은 아니다.
            self.exit()
        elif command == "/help":
            self._add("assistant", "/help   /providers (/models)   /use <provider> [model]   /plugins   /clear   /quit\n\n/use and /clear start a fresh session. Plugins run only when explicitly enabled.")
        elif command in {"/providers", "/models"}:
            # 원격 모델 목록을 조회하지 않고 사용자가 설정한 프로필만 보여 준다.
            try:
                providers = load_providers(self.config_path)
            except Exception as exc:
                self._add("error", f"{type(exc).__name__}: {exc}")
                return
            if not providers:
                self._add("assistant", "No providers configured.")
            else:
                self._add("assistant", "\n".join(f"{key} · {p.name} · {p.model} · {p.api_format}" for key, p in sorted(providers.items())))
        elif command == "/plugins":
            # 설정 파일의 후보가 아니라 현재 Agent가 선택한 진입점 목록을 표시한다.
            active = self.agent.plugins if self.agent else []
            self._add("assistant", "\n".join(active) if active else "No active plugins.")
        elif command == "/clear":
            # 새 Agent를 만들므로 선택된 플러그인의 setup도 다시 실행된다.
            if self.provider and self._activate(self.provider):
                self._add("assistant", "Started a fresh session.")
        elif command == "/use":
            # 제공자와 선택적 모델 재정의는 이번 실행에만 반영하고 TOML을 덮어쓰지 않는다.
            name, _, model = arg.strip().partition(" ")
            if not name:
                self._add("error", "Usage: /use <provider> [model]")
                return
            try:
                provider = resolve_provider(name, model.strip() or None, self.config_path)
                if self._activate(provider):
                    self._add("assistant", f"Switched to {provider.name} · {provider.model}. Started a fresh session.")
            except Exception as exc:
                self._add("error", f"{type(exc).__name__}: {exc}")
        else:
            self._add("error", f"Unknown command: {command}")

    @work(thread=True, group="agent")
    def run_agent(self, agent: Agent, prompt: str) -> None:
        # 동기 HTTP 요청과 셸 실행이 UI 갱신을 막지 않도록 별도 스레드에서 처리한다.
        # 호출 당시의 Agent를 인자로 받아 작업과 세션의 연결을 명시한다.
        try:
            self.call_from_thread(self._add, "tool", "working…")
            agent.ask(prompt)
        except Exception as exc:
            # API·플러그인 등의 실패를 표시하고 자동 재시도 없이 사용자에게 제어를 돌려준다.
            if self.is_running:
                self.call_from_thread(self._add, "error", f"{type(exc).__name__}: {exc}")
        finally:
            # 성공과 실패 모두 입력 잠금을 해제하고, UI가 이미 닫혔다면 연결을 정리한다.
            if self.is_running:
                self.call_from_thread(self._finished)
            else:
                agent.close()

    def _finished(self) -> None:
        # busy 변경도 UI 스레드에서 수행해 입력 처리와 상태 변경 순서를 맞춘다.
        self.busy = False


def run(provider: ProviderConfig | None = None, *, config_path: Path | None = None, plugins: list[str] | None = None) -> None:
    # argparse나 외부 호출부가 Textual 객체 생성 세부 사항을 알 필요 없도록 감싼다.
    LightweightHarnessApp(provider, config_path=config_path, plugins=plugins).run()
