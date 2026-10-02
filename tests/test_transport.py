# 모의 HTTP 응답으로 인증·경로·도구 스키마·대화 변환을 확인하며 실제 제공자에는 접속하지 않는다.
import json

import httpx

from lightweight_harness.agent import Agent
from lightweight_harness.providers import ProviderConfig


def test_anthropic_round_trip_preserves_blocks_and_groups_tool_results(tmp_path, monkeypatch):
    # 의미를 해석하지 않는 서명 블록과 성공·실패 도구 호출을 한 응답에 섞어 왕복 보존을 검사한다.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_ANTHROPIC_KEY", "test-key")
    native_blocks = [
        {"type": "thinking", "thinking": "test", "signature": "opaque-signature"},
        {"type": "text", "text": "Running commands."},
        {"type": "tool_use", "id": "a", "name": "run_command", "input": {"command": "printf hello > a.txt"}},
        {"type": "tool_use", "id": "b", "name": "run_command", "input": {}},
    ]
    replies = [{"content": native_blocks}, {"content": [{"type": "text", "text": "done"}]}]
    requests = []
    def respond(request):
        # OpenAI 인증 헤더가 섞이지 않고 Anthropic 전용 경로와 헤더를 쓰는지 확인한다.
        assert request.url == "https://anthropic.test/v1/messages"
        assert request.headers["x-api-key"] == "test-key"
        assert request.headers["anthropic-version"] == "2023-06-01"
        assert "authorization" not in request.headers
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=replies.pop(0))
    provider = ProviderConfig("Claude", "https://anthropic.test/v1", "TEST_ANTHROPIC_KEY", "test-model", "anthropic", 1234)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        Agent(provider, client=client).ask("test")
    # 기본 system 부재, 단일 도구 스키마, 출력 토큰 설정을 첫 요청에서 확인한다.
    assert "system" not in requests[0]
    assert requests[0]["max_tokens"] == 1234
    assert [tool["name"] for tool in requests[0]["tools"]] == ["run_command"]
    assert "input_schema" in requests[0]["tools"][0]
    # 후속 요청은 원본 assistant 블록과 호출 순서에 맞는 user 도구 결과를 유지해야 한다.
    assert requests[1]["messages"][1] == {"role": "assistant", "content": native_blocks}
    results = requests[1]["messages"][2]
    assert results["role"] == "user"
    assert [block["tool_use_id"] for block in results["content"]] == ["a", "b"]
    assert not results["content"][0]["is_error"]
    assert results["content"][1]["is_error"]
    assert (tmp_path / "a.txt").read_text() == "hello"


def test_openai_transport_uses_custom_endpoint_and_optional_auth(monkeypatch):
    # 무인증 로컬 서버와 키가 있는 사용자 정의 서버를 같은 전송 함수로 처리하는지 확인한다.
    requests = []
    def respond(request):
        # 본문 변환보다 URL과 인증 헤더가 관심사이므로 원래 요청 객체를 보관한다.
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "done"}}]})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        Agent(ProviderConfig("local", "http://localhost:1234/v1/", "", "local-model"), client=client).ask("test")
        monkeypatch.setenv("CUSTOM_KEY", "test-key")
        Agent(ProviderConfig("remote", "https://custom.test/api/v1/", "CUSTOM_KEY", "remote-model"), client=client).ask("test")
    assert requests[0].url == "http://localhost:1234/v1/chat/completions"
    assert "authorization" not in requests[0].headers
    assert requests[1].url == "https://custom.test/api/v1/chat/completions"
    assert requests[1].headers["authorization"] == "Bearer test-key"
