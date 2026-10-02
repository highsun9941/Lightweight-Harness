# CLI 인자가 제공자 선택과 UI 시작 함수까지 올바르게 전달되는지 확인한다.
import sys

import pytest

from lightweight_harness.app import main
from lightweight_harness.providers import NoProviderError


def test_main_starts_ui_without_provider(monkeypatch) -> None:
    # 설정이 없는 첫 실행에도 UI를 띄워 사용자가 도움말을 볼 수 있어야 한다.
    started = []

    def no_provider(*_args):
        # 일반 설정 오류가 아닌 '프로필 없음' 예외를 의도적으로 재현한다.
        raise NoProviderError("No provider configured. Add config")

    monkeypatch.setattr("lightweight_harness.app.resolve_provider", no_provider)
    monkeypatch.setattr("lightweight_harness.app.load_config", lambda *_args: {})
    # 실제 터미널 UI를 열지 않고 전달된 제공자 값만 수집한다.
    monkeypatch.setattr("lightweight_harness.app.run", lambda provider, **_kwargs: started.append(provider))
    monkeypatch.setattr(sys, "argv", ["lightweight-harness"])

    assert main() == 0
    assert started == [None]


def test_main_passes_provider_and_model_override(monkeypatch) -> None:
    # CLI가 명시한 제공자·모델을 누락하거나 임의 기본값으로 바꾸지 않는지 확인한다.
    captured = {}

    class Provider:
        # UI에 전달되는 객체의 정체만 확인하면 되므로 실제 API 설정은 만들지 않는다.
        name = "Test"
        model = "model-2"

    monkeypatch.setattr(
        "lightweight_harness.app.resolve_provider",
        lambda name, model, path: captured.update(name=name, model=model) or Provider(),
    )
    monkeypatch.setattr("lightweight_harness.app.load_config", lambda *_args: {})
    monkeypatch.setattr("lightweight_harness.app.run", lambda provider, **_kwargs: captured.update(provider=provider))
    monkeypatch.setattr(sys, "argv", ["lightweight-harness", "--provider", "custom", "--model", "model-2"])

    assert main() == 0
    assert captured["name"] == "custom"
    assert captured["model"] == "model-2"
    assert isinstance(captured["provider"], Provider)


@pytest.mark.parametrize("disabled", [False, True])
def test_explicit_config_and_plugin_selection(tmp_path, monkeypatch, disabled):
    # 설정 파일 뒤에 CLI 플러그인을 추가하고, --no-plugins는 두 출처를 모두 끄는지 검사한다.
    config = tmp_path / "config.toml"
    # 실제 TOML 파싱도 거치되 무인증 로컬 프로필을 사용해 API 키에 의존하지 않는다.
    config.write_text('''[plugins]
enabled = ["configured_plugin:setup"]
[providers.local]
base_url = "http://localhost:1234/v1"
api_key_env = ""
model = "local"
''')
    captured = {}
    monkeypatch.setattr("lightweight_harness.app.run", lambda provider, **kwargs: captured.update(provider=provider, **kwargs))
    args = ["lightweight-harness", "--config", str(config), "--plugin", "explicit_plugin:setup"]
    monkeypatch.setattr(sys, "argv", args + (["--no-plugins"] if disabled else []))
    assert main() == 0
    assert captured["config_path"] == config
    assert captured["provider"].model == "local"
    assert captured["plugins"] == ([] if disabled else ["configured_plugin:setup", "explicit_plugin:setup"])
