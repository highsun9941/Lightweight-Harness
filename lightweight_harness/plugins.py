# 사용자가 선택한 Python 진입점만 로딩한다. 설치·자동 탐색·실행 격리는 수행하지 않는다.
from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 타입 검사에만 Agent가 필요하다. 런타임 import 순환을 피한다.
    from .agent import Agent


def load_plugins(agent: Agent, specs: list[str]) -> None:
    """명시적으로 선택한 module:setup 진입점을 순서대로 초기화한다."""
    # set 대신 dict를 써서 중복을 없애도 사용자가 지정한 초기화 순서를 유지한다.
    for spec in dict.fromkeys(specs):
        # 모듈과 함수를 명시하게 해 저장소나 설치 패키지의 임의 코드를 자동 실행하지 않는다.
        module, separator, attribute = spec.partition(":")
        if not module or not separator or not attribute:
            raise ValueError(f"Invalid plugin '{spec}'; expected module:setup")
        try:
            # 일반 Python import와 함수 호출이므로 플러그인은 CLI와 같은 권한을 갖는다.
            setup = getattr(import_module(module), attribute)
            setup(agent)
        except Exception as exc:
            # 어느 플러그인이 실패했는지 표시하고 원래 예외 원인도 연결해 둔다.
            raise RuntimeError(f"Could not load plugin '{spec}': {exc}") from exc
