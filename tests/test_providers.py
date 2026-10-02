# 네트워크 호출 없이 TOML·환경변수·CLI 선택이 만드는 최종 제공자 설정을 확인한다.
from pathlib import Path

import pytest

from lightweight_harness.providers import ProviderConfig, load_config, load_providers, resolve_provider


def test_load_custom_provider(tmp_path: Path):
    # 코어에 이름이 등록되지 않은 서버도 TOML 프로필만으로 사용할 수 있어야 한다.
    config = tmp_path / "config.toml"
    config.write_text(
        """
[providers.deepseek]
name = "DeepSeek"
base_url = "https://api.deepseek.com/v1"
api_key_env = "DEEPSEEK_API_KEY"
model = "deepseek-chat"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    providers = load_providers(config)
    assert providers["deepseek"].base_url == "https://api.deepseek.com/v1"
    assert providers["deepseek"].model == "deepseek-chat"


def test_resolve_provider_from_config(tmp_path: Path, monkeypatch):
    # 기본 설정 경로를 임시 파일로 바꿔 명시한 프로필 이름이 올바른 설정을 선택하는지 확인한다.
    config = tmp_path / "config.toml"
    config.write_text(
        """
[providers.custom]
name = "Custom"
base_url = "https://example.com/v1"
api_key_env = "CUSTOM_API_KEY"
model = "custom-model"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("lightweight_harness.providers.DEFAULT_CONFIG", config)
    provider = resolve_provider("custom")
    assert provider.name == "Custom"
    assert provider.model == "custom-model"


def test_profile_selection_and_model_override_precedence(tmp_path, monkeypatch):
    # 이름순 첫 프로필과 다른 default_provider를 두어 기본값 우선순위도 함께 검증한다.
    config = tmp_path / "profiles.toml"
    config.write_text('''default_provider = "z"
[providers.a]
base_url = "http://localhost:1234/v1"
api_key_env = ""
model = "local-model"
[providers.z]
base_url = "https://claude.test/v1"
api_key_env = "CLAUDE_KEY"
model = "configured-model"
api_format = "anthropic"
max_tokens = 8192
''')
    monkeypatch.setenv("LIGHTWEIGHT_HARNESS_CONFIG", str(config))
    assert resolve_provider().model == "configured-model"
    # 모델은 프로필 → 환경변수 → CLI 순서로 덮어쓰되 전송 형식과 토큰 상한은 보존해야 한다.
    monkeypatch.setenv("LIGHTWEIGHT_HARNESS_MODEL", "env-model")
    assert resolve_provider().model == "env-model"
    selected = resolve_provider(model="cli-model")
    assert selected.model == "cli-model"
    assert selected.api_format == "anthropic" and selected.max_tokens == 8192
    # 제공자 환경변수와 명시적 이름의 우선순위, 무인증 선택도 확인한다.
    monkeypatch.setenv("LIGHTWEIGHT_HARNESS_PROVIDER", "a")
    assert resolve_provider().api_key() == ""
    assert resolve_provider("z").api_format == "anthropic"


def test_empty_compose_environment_uses_builtin_defaults(monkeypatch):
    # Compose의 ${VAR:-}가 만드는 빈 문자열도 환경변수 미설정과 같은 기본값을 사용해야 한다.
    monkeypatch.setenv("LIGHTWEIGHT_HARNESS_MODEL", "")
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    assert resolve_provider().model == "gpt-5"
    assert resolve_provider().base_url == "https://api.openai.com/v1"


def test_explicit_missing_config_is_not_silently_ignored(tmp_path):
    # 사용자가 지정한 파일의 오타를 빈 설정으로 처리하면 다른 서버에 연결될 수 있다.
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        load_config(tmp_path / "typo.toml")


def test_keyless_provider_is_explicit(monkeypatch):
    # 환경변수 이름을 지정해 놓고 값만 없는 경우는 무인증 프로필과 구분해 오류를 내야 한다.
    provider = ProviderConfig("local", "http://localhost/v1", "NEEDED_KEY", "model")
    monkeypatch.delenv("NEEDED_KEY", raising=False)
    with pytest.raises(RuntimeError, match="NEEDED_KEY"):
        provider.api_key()


def test_unknown_api_format_fails_at_configuration_time():
    # 지원하지 않는 형식은 첫 API 요청까지 기다리지 않고 설정 객체 생성 시 거절한다.
    with pytest.raises(ValueError, match="API format"):
        ProviderConfig("test", "https://test/v1", "", "model", "typo")
