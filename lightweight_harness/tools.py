# 모델에 노출할 기본 도구는 셸 실행 하나다. 파일 작업도 모델이 셸 명령으로 구성한다.
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def run_command(command: str) -> str:
    # 파이프·리다이렉션 등을 사용할 수 있도록 셸에 명령을 그대로 전달한다.
    # 현재 프로세스의 권한으로 실행하며, cwd는 시작 위치일 뿐 파일 접근 경계가 아니다.
    # 호출마다 새 셸을 쓰므로 cd나 export의 효과는 다음 호출까지 유지되지 않는다.
    # 명령 종료까지 기다린 뒤 출력을 모은다. 스트리밍·타임아웃·프로세스 제어 기능은 없다.
    result = subprocess.run(command, shell=True, cwd=Path.cwd(), text=True, capture_output=True)
    # stdout 뒤에 stderr를 붙이므로 두 스트림의 실제 발생 순서는 보존하지 않는다.
    # strip은 바깥쪽 공백·개행을 제거한다. 따라서 원본 바이트를 그대로 반환하는 도구는 아니다.
    output = (result.stdout + result.stderr).strip()
    # 출력이 없어도 성공·실패를 판단할 단서를 제공하고, 다음 행동은 모델이 정하게 한다.
    return f"exit_code={result.returncode}\n{output}" if output else f"exit_code={result.returncode}"


# 이 스키마만 API에 전달된다. 아래의 설명 문자열은 모델이 실제로 읽는 도구 계약이다.
# additionalProperties는 허용 인자를 command로 제한해 주지만 명령 자체를 검사하지는 않는다.
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function", "function": {
            "name": "run_command",
            "description": "Run a shell command in the current working directory and return its exit code, stdout, and stderr.",
            "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"], "additionalProperties": False},
        },
    },
]


def execute_tool(name: str, args: dict[str, Any]) -> str:
    # 임의의 Python 함수 이름을 찾지 않고 명시된 기본 도구만 실행한다.
    if name == "run_command":
        return run_command(**args)
    # 잘못된 이름은 Agent가 도구 오류로 모델에 돌려주도록 예외로 표시한다.
    raise ValueError(f"unknown tool: {name}")
