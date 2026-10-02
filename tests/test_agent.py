# 모델의 능력을 평가하는 테스트가 아니라, 정해진 API 응답에 대한 코어의 실행 계약을 확인한다.
import json
import shlex
import sys
from types import ModuleType

import httpx
import pytest

from lightweight_harness.agent import Agent
from lightweight_harness.providers import ProviderConfig


def call(name, arguments, call_id="call_1"):
    # 실제 API의 도구 호출 모양을 재사용해 테스트별로 관심 있는 이름·인자만 바꾸게 한다.
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


def client_for(replies, requests):
    # 네트워크 없이 요청 내용을 수집하고 준비한 응답을 차례대로 반환한다.
    def respond(request):
        # 후속 요청에 도구 결과가 들어갔는지 검증할 수 있도록 JSON 본문을 저장한다.
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": replies.pop(0)}]})
    return httpx.Client(transport=httpx.MockTransport(respond))


# MockTransport를 사용하므로 실제 키가 필요 없는 공통 테스트 프로필이다.
PROVIDER = ProviderConfig("test", "https://provider.test/v1", "", "test-model")


def test_default_request_has_only_user_history_and_shell_tool(tmp_path, monkeypatch):
    # 지침 파일이 실제로 있어도 자동 주입하지 않고, 기본 도구는 셸 하나인지 확인한다.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "AGENTS.md").write_text("INSTRUCTIONS THAT MUST NOT BE INJECTED")
    requests = []
    with client_for([{"role": "assistant", "content": "done"}], requests) as client:
        agent = Agent(PROVIDER, client=client)
        assert agent.messages == []
        agent.ask("hello")
    assert requests[0]["messages"] == [{"role": "user", "content": "hello"}]
    assert [tool["function"]["name"] for tool in requests[0]["tools"]] == ["run_command"]
    assert agent.plugins == []


def test_multiple_shell_calls_execute_and_full_results_return_to_model(tmp_path, monkeypatch):
    # 쓰기 다음 읽기의 순서와 호출 ID 연결을 검증하고, UI 표시 한도보다 긴 결과를 사용한다.
    monkeypatch.chdir(tmp_path)
    requests, events = [], []
    text = "x" * 2000
    replies = [
        {"role": "assistant", "content": None, "tool_calls": [
            call("run_command", json.dumps({"command": f"printf %s {shlex.quote(text)} > a.txt"})),
            call("run_command", '{"command":"cat a.txt"}', "call_2"),
        ]},
        {"role": "assistant", "content": "done"},
    ]
    with client_for(replies, requests) as client:
        Agent(PROVIDER, events.append, client=client).ask("write and read")
    assert (tmp_path / "a.txt").read_text() == text
    results = requests[1]["messages"][2:]
    assert [m["tool_call_id"] for m in results] == ["call_1", "call_2"]
    # 모델에는 전체 결과가 전달돼야 하며 OpenAI 요청에 내부 오류 필드가 섞이면 안 된다.
    assert results[1]["content"] == "exit_code=0\n" + text
    assert "_is_error" not in results[0]
    assert events[-1].kind == "turn_end"


@pytest.mark.parametrize("name,arguments", [
    # 깨진 JSON, 객체가 아닌 인자, 필수 인자 누락, 제거된 도구 호출을 각각 검사한다.
    ("run_command", "{"), ("run_command", "[]"), ("run_command", "{}"), ("read_file", "{}"),
])
def test_bad_tool_calls_return_errors_without_breaking_history(name, arguments):
    # 실행 오류 뒤에도 원래 호출 ID와 연결된 결과가 있어 모델이 후속 응답을 할 수 있어야 한다.
    requests = []
    replies = [{"role": "assistant", "tool_calls": [call(name, arguments)]},
               {"role": "assistant", "content": "handled"}]
    with client_for(replies, requests) as client:
        Agent(PROVIDER, client=client).ask("test")
    assert requests[1]["messages"][-1]["content"].startswith("ERROR:")
    assert requests[1]["messages"][-1]["tool_call_id"] == "call_1"


def test_plugins_are_explicit_and_do_not_leak_between_agents(monkeypatch):
    # 설치된 모듈을 흉내 내되 sys.modules 변경은 monkeypatch가 테스트 후 되돌린다.
    module = ModuleType("test_optional_plugin")
    loads, events, requests = [], [], []

    def setup(agent):
        # 초기화 횟수, 추가 도구, 요청 전 훅, 이벤트 구독을 하나의 작은 플러그인으로 검사한다.
        loads.append(agent)
        agent.add_tool({"type": "function", "function": {
            "name": "echo", "description": "Echo text.",
            "parameters": {"type": "object", "properties": {"text": {"type": "string"}}},
        }}, lambda text: text)
        def context(current):
            # 훅은 요청마다 실행되므로 같은 지침이 계속 쌓이지 않게 한 번만 넣는다.
            if current.messages[0]["role"] != "system":
                current.messages.insert(0, {"role": "system", "content": "opt-in context"})
        agent.before_request.append(context)
        agent.event_handlers.append(events.append)

    module.setup = setup
    monkeypatch.setitem(sys.modules, module.__name__, module)
    replies = [{"role": "assistant", "tool_calls": [call("echo", '{"text":"hello"}')]},
               {"role": "assistant", "content": "done"}]
    with client_for(replies, requests) as client:
        bare = Agent(PROVIDER, client=client)
        assert loads == []
        extended = Agent(PROVIDER, plugins=["test_optional_plugin:setup"] * 2, client=client)
        extended.ask("test")
        # 중복 진입점은 한 번만 초기화되고 기본 Agent의 목록은 변하지 않아야 한다.
        assert len(loads) == 1
        assert len(bare.tools) == 1 and bare.messages == []
        assert len(extended.tools) == 2
    assert requests[0]["messages"][0]["content"] == "opt-in context"
    assert requests[1]["messages"][-1]["content"] == "hello"
    assert events[-1].kind == "turn_end"


def test_missing_plugin_is_an_explicit_failure():
    # 선택한 확장이 없는데 기본 코어로 조용히 계속 실행되는 일을 막는다.
    with client_for([], []) as client:
        with pytest.raises(RuntimeError, match="Could not load plugin"):
            Agent(PROVIDER, plugins=["missing_lightweight_harness_test_plugin:setup"], client=client)


def test_http_errors_are_not_retried():
    # 서버의 429 응답을 그대로 알리고 런타임이 추가 요청을 만들지 않는지 확인한다.
    requests = []
    def reject(request):
        # 요청 횟수를 세어 응답 오류와 숨겨진 재시도를 구분한다.
        requests.append(request)
        return httpx.Response(429)
    with httpx.Client(transport=httpx.MockTransport(reject)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            Agent(PROVIDER, client=client).ask("test")
    assert len(requests) == 1
