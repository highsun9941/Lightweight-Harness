# 모든 테스트가 사용자의 실제 API 키나 홈 디렉터리 설정에 의존하지 않도록 공통 환경을 만든다.
import pytest


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """환경변수 단축 설정과 기본 설정 경로를 테스트마다 격리한다."""
    # autouse이므로 테스트가 직접 요청하지 않아도 적용되고 monkeypatch가 종료 후 복원한다.
    for name in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "LIGHTWEIGHT_HARNESS_API_KEY",
                 "LIGHTWEIGHT_HARNESS_PROVIDER", "LIGHTWEIGHT_HARNESS_MODEL", "LIGHTWEIGHT_HARNESS_CONFIG", "OPENAI_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    # 기본 파일은 없는 상태로 두고 필요한 테스트만 자신의 임시 설정 파일을 지정한다.
    monkeypatch.setattr("lightweight_harness.providers.DEFAULT_CONFIG", tmp_path / "missing.toml")
