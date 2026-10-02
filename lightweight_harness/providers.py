# 제공자 선택을 설정 데이터로 처리해 새 API 주소를 추가할 때 코어를 수정하지 않게 한다.
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


# 프로젝트 파일을 자동 탐색하지 않고 사용자 설정 경로 하나를 기본값으로 사용한다.
DEFAULT_CONFIG = Path.home() / ".config" / "lightweight-harness" / "config.toml"


@dataclass(frozen=True)
class ProviderConfig:
    # 불변 객체로 만들어 세션별 모델 재정의가 원래 프로필을 바꾸지 않도록 한다.
    # api_key_env에는 키 자체가 아니라 키를 읽을 환경변수의 이름을 보관한다.
    name: str
    base_url: str
    api_key_env: str
    model: str
    api_format: str = "openai"
    max_tokens: int = 4096

    def __post_init__(self) -> None:
        # 전송 코드가 처리할 수 없는 형식과 기본 설정 오류를 API 호출 전에 발견한다.
        if self.api_format not in {"openai", "anthropic"}:
            raise ValueError(f"Unknown API format: {self.api_format}")
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("Provider base_url must start with http:// or https://")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("Provider model must be a nonempty string")
        # bool도 int의 하위 타입이므로 정확한 타입 비교로 True를 토큰 수로 받지 않는다.
        if type(self.max_tokens) is not int or self.max_tokens <= 0:
            raise ValueError("Provider max_tokens must be a positive integer")

    def api_key(self) -> str:
        # 빈 이름을 명시한 프로필만 무인증 서버로 취급한다.
        if not self.api_key_env:
            return ""
        # 실제 요청 시 환경변수에서 읽는다. 키 누락을 무인증 요청으로 조용히 바꾸지 않는다.
        value = os.getenv(self.api_key_env)
        if not value:
            raise RuntimeError(f"Missing API key environment variable: {self.api_key_env}")
        return value


def _builtins() -> dict[str, ProviderConfig]:
    # TOML 없이 시작할 수 있게 알려진 키 환경변수에 대해서만 기본 프로필을 만든다.
    providers: dict[str, ProviderConfig] = {}
    if os.getenv("OPENAI_API_KEY") or os.getenv("LIGHTWEIGHT_HARNESS_API_KEY"):
        # Lightweight-Harness 전용 키가 있으면 우선 사용하고, 빈 주소·모델 변수는 기본값으로 보완한다.
        providers["openai"] = ProviderConfig("OpenAI", os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1", "LIGHTWEIGHT_HARNESS_API_KEY" if os.getenv("LIGHTWEIGHT_HARNESS_API_KEY") else "OPENAI_API_KEY", os.getenv("LIGHTWEIGHT_HARNESS_MODEL") or "gpt-5")
    if os.getenv("OPENROUTER_API_KEY"):
        # OpenRouter도 동일한 OpenAI 호환 전송을 사용하며 주소와 모델 이름만 다르다.
        providers["openrouter"] = ProviderConfig("OpenRouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", os.getenv("LIGHTWEIGHT_HARNESS_MODEL") or "openai/gpt-5")
    return providers


def load_config(path: Path | None = None) -> dict[str, Any]:
    # CLI 경로 → 환경변수 → 기본 경로 순서로 선택한다.
    explicit_path = path is not None or bool(os.getenv("LIGHTWEIGHT_HARNESS_CONFIG"))
    path = path or Path(os.getenv("LIGHTWEIGHT_HARNESS_CONFIG") or DEFAULT_CONFIG)
    if path.exists():
        # 표준 라이브러리로 TOML을 읽어 설정 파서 의존성을 추가하지 않는다.
        return tomllib.loads(path.read_text(encoding="utf-8"))
    if explicit_path:
        # 사용자가 직접 지정한 경로의 오타는 오류로 알린다.
        raise FileNotFoundError(f"Config file not found: {path}")
    # 기본 파일이 없는 첫 실행은 허용해 환경변수만으로도 사용할 수 있다.
    return {}


def _configured_providers(data: dict[str, Any]) -> dict[str, ProviderConfig]:

    # 환경변수 단축 설정보다 같은 이름의 TOML 프로필을 우선한다.
    providers = _builtins()
    for key, raw in data.get("providers", {}).items():
        providers[key] = ProviderConfig(
            # 프로필 키는 선택용 식별자이고 name은 UI에 표시할 이름이다.
            name=raw.get("name", key),
            # 전송 계층에서 /messages 또는 /chat/completions를 붙이므로 끝의 /를 정리한다.
            base_url=raw["base_url"].rstrip("/"),
            api_key_env=raw.get("api_key_env", "OPENAI_API_KEY"),
            model=raw["model"],
            api_format=raw.get("api_format", "openai"),
            max_tokens=raw.get("max_tokens", 4096),
        )
    return providers


def load_providers(path: Path | None = None) -> dict[str, ProviderConfig]:
    # UI의 목록 표시도 실제 선택과 동일한 병합 규칙을 사용한다.
    return _configured_providers(load_config(path))


class NoProviderError(RuntimeError):
    # 설정 자체의 오류와 '아직 프로필이 없음'을 구분해 후자만 UI 시작 시 허용한다.
    pass


def resolve_provider(
    provider_name: str | None = None,
    model: str | None = None,
    path: Path | None = None,
) -> ProviderConfig:
    # 선택할 때 설정을 다시 읽어 명시한 파일의 현재 프로필을 사용한다.
    data = load_config(path)
    providers = _configured_providers(data)
    # 제공자는 CLI → 환경변수 → 설정 기본값, 모델은 CLI → 환경변수 → 프로필 순서다.
    name = provider_name or os.getenv("LIGHTWEIGHT_HARNESS_PROVIDER") or data.get("default_provider")
    model = model or os.getenv("LIGHTWEIGHT_HARNESS_MODEL")
    if name:
        if name not in providers:
            # 지정한 제공자가 없을 때 다른 서버로 임의 연결하지 않고 선택 오류를 알린다.
            available = ", ".join(sorted(providers)) or "none"
            raise RuntimeError(f"Unknown provider '{name}'. Available: {available}")
        provider = providers[name]
        # 기존 불변 프로필을 보존하면서 이번 선택에만 모델 재정의를 반영한다.
        return replace(provider, model=model or provider.model)
    if not providers:
        raise NoProviderError("No provider configured. Add one to ~/.config/lightweight-harness/config.toml or set a supported API key environment variable.")
    # 기본값을 지정하지 않아도 매번 같은 프로필을 고르도록 키 이름순으로 선택한다.
    first = providers[sorted(providers)[0]]
    return replace(first, model=model or first.model)
