# Textual의 가상 화면에서 세션 수명과 입력 제어를 검사한다. 모델 API 호출은 가짜 Agent로 대체한다.
import asyncio
import threading

from textual.widgets import Input

from lightweight_harness.providers import ProviderConfig
from lightweight_harness.tui import LightweightHarnessApp


class FakeAgent:
    # UI가 사용하는 속성과 close만 구현해 세션 교체·연결 정리 여부를 관찰한다.
    instances = []

    def __init__(self, provider, on_event, *, plugins):
        # 실제 플러그인을 로딩하지 않고 UI가 전달한 선택과 새 대화 상태만 보관한다.
        self.provider = provider
        self.plugins = plugins
        self.closed = False
        self.messages = []
        self.instances.append(self)

    def close(self):
        # 연결 대신 상태 플래그로 닫힌 시점을 확인한다.
        self.closed = True


def test_switch_uses_selected_config_and_preserves_plugin_selection(tmp_path, monkeypatch):
    # /use가 명시한 설정 파일을 사용하고, 세션 변경 시 플러그인 선택을 유지하는지 확인한다.
    config = tmp_path / "profiles.toml"
    config.write_text('''[providers.second]
name = "Second"
base_url = "http://localhost/v1"
api_key_env = ""
model = "second-model"
''')
    monkeypatch.setattr("lightweight_harness.tui.Agent", FakeAgent)
    first = ProviderConfig("First", "http://localhost/v1", "", "first-model")

    async def scenario():
        # 실제 터미널 없이 위젯 생명주기와 명령 처리를 실행한다.
        app = LightweightHarnessApp(first, config_path=config, plugins=["example:setup"])
        async with app.run_test() as pilot:
            old = app.agent
            app._command("/use second override")
            assert old.closed
            assert app.provider.model == "override"
            assert app.agent.plugins == ["example:setup"]
            active = app.agent
            # 잘못된 제공자와 작업 중 세션 변경 시도는 현재 세션을 닫으면 안 된다.
            app._command("/use missing")
            assert app.agent is active and not active.closed
            app.busy = True
            app._command("/use second")
            app._command("/clear")
            assert app.agent is active
            app.busy = False
            app._command("/clear")
            assert active.closed
            # 모델 출력 같은 대괄호 텍스트도 마크업 오류 없이 표시할 수 있어야 한다.
            app._add("assistant", "[not-markup] literal [/broken]")
            await pilot.pause()
        assert app.agent.closed
    asyncio.run(scenario())


def test_busy_task_does_not_start_overlapping_requests(monkeypatch):
    # 실제 스레드 동기화로 첫 요청을 대기시켜 두고 두 번째 입력이 실행되지 않는지 확인한다.
    started, release = threading.Event(), threading.Event()
    prompts = []

    class SlowAgent(FakeAgent):
        # 외부 호출 없이 실행 중인 작업을 재현한다.
        def ask(self, prompt):
            # 이벤트로 실행 시작을 알리고 테스트가 해제할 때까지 잠시 대기한다.
            prompts.append(prompt)
            started.set()
            release.wait(timeout=5)

    monkeypatch.setattr("lightweight_harness.tui.Agent", SlowAgent)
    provider = ProviderConfig("Test", "http://localhost/v1", "", "model")

    async def scenario():
        # Textual 작업 스레드와 UI 입력 이벤트가 겹치는 상황을 만든다.
        app = LightweightHarnessApp(provider)
        async with app.run_test() as pilot:
            composer = app.query_one(Input)
            app.on_input_submitted(Input.Submitted(composer, "first"))
            assert app.busy
            try:
                await asyncio.to_thread(started.wait, 2)
                app.on_input_submitted(Input.Submitted(composer, "second"))
                assert prompts == ["first"]
            finally:
                # 검증 실패 시에도 대기 스레드를 풀어 테스트가 멈추지 않게 한다.
                release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert not app.busy
    asyncio.run(scenario())
