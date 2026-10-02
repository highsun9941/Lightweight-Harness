# 대화와 도구 호출의 순서를 연결하는 코어다. 계획·재시도·대화 압축 정책은 넣지 않는다.
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from .providers import ProviderConfig
from .plugins import load_plugins
from .tools import TOOL_DEFINITIONS, execute_tool
from .transport import complete


@dataclass
class AgentEvent:
    # UI와 플러그인이 같은 사건을 구독하도록 표시용 데이터를 작은 객체로 전달한다.
    kind: str
    text: str = ""
    tool: str = ""


class Agent:
    # Agent 하나가 제공자 하나와 현재 세션의 대화를 소유한다.
    def __init__(
        self,
        provider: ProviderConfig,
        on_event: Callable[[AgentEvent], None] | None = None,
        *,
        plugins: list[str] | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.provider = provider
        # UI가 없는 테스트·외부 호출에서도 같은 코어를 사용할 수 있도록 기본 콜백은 비워 둔다.
        self.on_event = on_event or (lambda _event: None)
        # 기본 대화를 빈 목록으로 시작해 코어의 시스템 프롬프트·저장소 지침을 주입하지 않는다.
        self.messages: list[dict[str, Any]] = []
        # 중첩된 도구 스키마까지 복사해 플러그인의 변경이 다른 세션에 새지 않게 한다.
        self.tools = deepcopy(TOOL_DEFINITIONS)
        # 기본 도구 실행과 선택형 플러그인의 실행 함수를 구분해 보관한다.
        self.tool_handlers: dict[str, Callable[..., str]] = {}
        # 필요한 정책만 플러그인이 등록한다. 기본값에서는 호출할 훅이 없다.
        self.before_request: list[Callable[[Agent], None]] = []
        self.event_handlers: list[Callable[[AgentEvent], None]] = []
        self.plugins = list(dict.fromkeys(plugins or []))
        # 세션 동안 HTTP 연결을 재사용한다. 외부 클라이언트를 받으면 모의 전송도 주입할 수 있다.
        # 180초는 HTTP 대기 설정이며, 전체 작업이나 셸 명령의 실행 시간 제한은 아니다.
        self.client = client or httpx.Client(timeout=180.0)
        self._owns_client = client is None
        try:
            # 명시적으로 선택한 플러그인만 새 세션 생성 시 한 번 초기화한다.
            load_plugins(self, self.plugins)
        except Exception:
            # 초기화가 실패해 Agent를 돌려주지 못해도 직접 만든 HTTP 연결은 정리한다.
            self.close()
            raise

    def close(self) -> None:
        # 주입받은 클라이언트의 수명은 호출자가 관리하므로 여기서 닫지 않는다.
        if self._owns_client:
            self.client.close()

    def add_tool(self, definition: dict[str, Any], handler: Callable[..., str]) -> None:
        # 이름은 모델의 호출과 실행 함수를 연결하는 키다. 중복 등록으로 덮어쓰지 않는다.
        name = definition["function"]["name"]
        if any(tool["function"]["name"] == name for tool in self.tools):
            raise ValueError(f"Tool already registered: {name}")
        self.tools.append(deepcopy(definition))
        # 스키마는 모델에 보내고, 실제 Python 함수는 런타임 안에만 보관한다.
        self.tool_handlers[name] = handler

    def _emit(self, event: AgentEvent) -> None:
        # 표시 콜백 뒤에 플러그인 구독자를 등록 순서대로 호출한다.
        # 콜백 실패를 숨기지 않으므로 예외가 나면 현재 작업이 중단될 수 있다.
        self.on_event(event)
        for handler in self.event_handlers:
            handler(event)

    def ask(self, prompt: str) -> None:
        # 이 목록은 프로세스 메모리에만 남는다. 저장·복원·요약은 기본 코어에서 하지 않는다.
        self.messages.append({"role": "user", "content": prompt})
        while True:
            # 도구 결과를 받은 뒤의 후속 요청에도 훅을 적용할 기회를 준다.
            for hook in self.before_request:
                hook(self)
            # HTTP 실패는 상위 UI로 전달한다. 자동 재요청으로 비용이나 행동을 늘리지 않는다.
            message = complete(self.client, self.provider, self.messages, self.tools)
            # 도구 결과보다 먼저 원래 호출을 기록해 API가 요구하는 대화 순서를 유지한다.
            self.messages.append(message)

            content = message.get("content")
            if content:
                self._emit(AgentEvent(kind="assistant", text=content))

            calls = message.get("tool_calls") or []
            if not calls:
                # 종료 조건은 도구 호출의 부재다. 목표 완수를 별도로 판정하거나 반복을 강제하지 않는다.
                self._emit(AgentEvent(kind="turn_end"))
                return

            # 같은 응답의 호출도 순서대로 실행해 파일 쓰기 후 읽기 같은 의존 관계를 보존한다.
            for call in calls:
                name = call["function"]["name"]
                arguments = call["function"].get("arguments", "{}")
                self._emit(AgentEvent(kind="tool_start", tool=name))
                failed = False
                try:
                    args = json.loads(arguments)
                    # 키워드 인자로 넘길 수 있는 JSON 객체만 허용한다.
                    if not isinstance(args, dict):
                        raise ValueError("Tool arguments must be a JSON object")
                    handler = self.tool_handlers.get(name)
                    result = handler(**args) if handler else execute_tool(name, args)
                    # 모든 도구 결과를 텍스트로 통일해 제공자별 응답 변환을 단순하게 유지한다.
                    if not isinstance(result, str):
                        raise TypeError("Tool results must be strings")
                except Exception as exc:
                    # 호출 오류도 해당 호출 ID의 결과로 반환해 모델이 다음 행동을 정하게 한다.
                    failed = True
                    result = f"ERROR: {type(exc).__name__}: {exc}"
                # 내부 오류 표시는 Anthropic 변환에 사용하고 OpenAI 요청에서는 제거한다.
                # 셸의 0이 아닌 종료 코드는 결과 문자열에 담기며 여기서 Python 예외로 취급하지 않는다.
                self.messages.append({"role": "tool", "tool_call_id": call["id"], "content": result, "_is_error": failed})
                self._emit(AgentEvent(kind="tool_end", tool=name, text=result))
