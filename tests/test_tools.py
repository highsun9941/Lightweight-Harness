# 셸 도구의 실제 파일 작업과 결과 형식을 임시 디렉터리·짧은 명령으로 확인한다.
from pathlib import Path

import pytest

from lightweight_harness.tools import execute_tool, run_command


def test_shell_can_write_and_read_files_in_working_directory(tmp_path: Path, monkeypatch):
    # 별도의 파일 도구 없이도 리다이렉션과 읽기를 한 명령에서 수행할 수 있어야 한다.
    monkeypatch.chdir(tmp_path)
    result = execute_tool("run_command", {"command": "printf 'hello\\n' > a.txt && cat a.txt"})
    assert result == "exit_code=0\nhello"
    assert (tmp_path / "a.txt").read_text() == "hello\n"


def test_shell_returns_exit_code_and_both_output_streams():
    # 실패한 명령도 종료 코드와 stdout·stderr를 돌려줘 모델이 원인을 판단할 수 있어야 한다.
    result = run_command("printf 'output\\n'; printf 'error\\n' >&2; exit 7")
    assert result == "exit_code=7\noutput\nerror"


@pytest.mark.parametrize("name", ["read_file", "write_file", "replace_in_file"])
def test_removed_file_tools_are_not_executable(name):
    # 스키마에서만 숨기고 실행 경로를 남겨 두는 실수를 막기 위해 이전 도구 이름을 직접 호출한다.
    with pytest.raises(ValueError, match=f"unknown tool: {name}"):
        execute_tool(name, {})
