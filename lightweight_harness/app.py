# 실행 옵션을 해석하고 초기 세션을 선택한다. 모델의 작업 계획은 여기서 정하지 않는다.
from __future__ import annotations

import argparse
from pathlib import Path

from .providers import NoProviderError, load_config, resolve_provider
from .tui import run


def main() -> int:
    # argparse가 도움말과 인자 오류를 처리하므로 별도의 명령 파서를 유지하지 않는다.
    parser = argparse.ArgumentParser(prog="lightweight-harness", description="A lightweight, model-driven coding harness")
    parser.add_argument("--provider", help="configured provider name")
    parser.add_argument("--model", help="override configured model")
    parser.add_argument("--config", type=Path, help="provider and plugin configuration file")
    # 같은 옵션을 반복해 여러 플러그인을 사용자가 지정한 순서대로 선택할 수 있다.
    parser.add_argument("--plugin", action="append", default=[], metavar="MODULE:SETUP", help="enable an installed plugin (repeatable)")
    parser.add_argument("--no-plugins", action="store_true", help="disable all configured and command-line plugins")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        # 비활성화 옵션은 설정 파일과 CLI 양쪽의 플러그인 선택보다 우선한다.
        plugins = [] if args.no_plugins else config.get("plugins", {}).get("enabled", [])
        # 문자열 하나를 문자 목록처럼 순회하는 등의 모호한 설정을 시작 단계에서 거절한다.
        if not isinstance(plugins, list) or not all(isinstance(spec, str) for spec in plugins):
            raise ValueError("plugins.enabled must be a list of module:setup strings")
        if not args.no_plugins:
            # 설정 파일 → CLI 순서를 유지하면서 같은 진입점의 중복 실행을 막는다.
            plugins = list(dict.fromkeys([*plugins, *args.plugin]))
        try:
            provider = resolve_provider(args.provider, args.model, args.config)
        except NoProviderError:
            # 첫 실행에 제공자가 없어도 UI의 도움말과 설정 안내를 볼 수 있게 한다.
            provider = None
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError) as exc:
        # 파일·형식·선택 오류는 모델에 보내지 않고 CLI 사용 오류로 보고한다.
        parser.error(str(exc))
    # 설정 경로와 플러그인 선택을 전달해 UI에서 세션을 바꿔도 같은 설정을 사용한다.
    run(provider, config_path=args.config, plugins=plugins)
    return 0
