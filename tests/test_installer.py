"""격리한 가짜 외부 명령으로 네트워크 없이 파이프 방식 설치를 검증한다."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


# 테스트의 작업 위치와 관계없이 저장소의 설치 스크립트를 찾는다.
SCRIPT = Path(__file__).resolve().parents[1] / "install.sh"


@pytest.fixture
def installer(tmp_path):
    # 설치 스크립트의 PATH를 제한해 개발 환경에 있는 uv나 Python에 의존하지 않게 한다.
    commands = tmp_path / "commands"
    commands.mkdir()
    for name in ("bash", "sh", "uname", "mkdir", "mktemp", "rm", "cp", "cat"):
        # 기본 셸 동작은 실제 명령을 쓰고 다운로드와 패키지 설치만 가짜 명령으로 대체한다.
        (commands / name).symlink_to(shutil.which(name))
    uv = tmp_path / "uv-stub"
    # 아래 Python 코드가 가짜 uv다. 인자·설치 경로를 JSONL에 기록하고 실패 조건을 흉내 낸다.
    # 성공하면 --help 검증에 응답할 수 있는 가짜 lightweight-harness 명령을 만든다.
    # shebang에 현재 Python의 절대 경로를 써서 제한된 PATH에 Python이 없어도 실행된다.
    uv.write_text(f"#!{sys.executable}\n" + '''
import json, os, pathlib, sys
with open(os.environ['LIGHTWEIGHT_HARNESS_TEST_UV_LOG'], 'a') as output:
    output.write(json.dumps({'args': sys.argv[1:],
        'tools': os.environ['UV_TOOL_DIR'],
        'python': os.environ['UV_PYTHON_INSTALL_DIR']}) + '\\n')
if os.environ.get('LIGHTWEIGHT_HARNESS_TEST_FAIL_UV'):
    sys.exit(41)
command = pathlib.Path(os.environ['UV_TOOL_BIN_DIR']) / 'lightweight-harness'
command.write_text('#!/bin/sh\\nexit 0\\n')
command.chmod(0o755)
''')
    uv.chmod(0o755)
    curl = commands / "curl"
    # 가짜 curl은 URL·인자를 기록하고 uv 복사만 수행하는 다운로드 결과를 만든다.
    # 실패할 때는 실행 시 흔적이 남는 내용을 써서 실패한 다운로드의 오실행을 탐지한다.
    curl.write_text(f"#!{sys.executable}\n" + '''
import json, os, pathlib, sys
path = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])
pathlib.Path(os.environ['LIGHTWEIGHT_HARNESS_TEST_CURL_LOG']).write_text(json.dumps(sys.argv[1:]))
if os.environ.get('LIGHTWEIGHT_HARNESS_TEST_FAIL_DOWNLOAD'):
    path.write_text('touch "' + os.environ['LIGHTWEIGHT_HARNESS_TEST_BAD_DOWNLOAD_MARKER'] + '"\\n')
    sys.exit(22)
path.write_text('mkdir -p "$UV_UNMANAGED_INSTALL"\\ncp "$LIGHTWEIGHT_HARNESS_TEST_UV_STUB" "$UV_UNMANAGED_INSTALL/uv"\\n')
''')
    curl.chmod(0o755)
    env = os.environ.copy()
    # 공백이 있는 설치 경로도 처리하는지 확인하고 출력·실행 흔적은 모두 임시 경로에 둔다.
    env.update({
        "PATH": str(commands),
        "LIGHTWEIGHT_HARNESS_INSTALL_DIR": str(tmp_path / "runtime with spaces"),
        "LIGHTWEIGHT_HARNESS_BIN_DIR": str(tmp_path / "bin with spaces"),
        "LIGHTWEIGHT_HARNESS_TEST_UV_STUB": str(uv),
        "LIGHTWEIGHT_HARNESS_TEST_UV_LOG": str(tmp_path / "uv.jsonl"),
        "LIGHTWEIGHT_HARNESS_TEST_CURL_LOG": str(tmp_path / "curl.json"),
        "LIGHTWEIGHT_HARNESS_TEST_BAD_DOWNLOAD_MARKER": str(tmp_path / "bad-download-executed"),
    })
    # 실행한 사람의 환경변수가 각 테스트의 ref 선택에 영향을 주지 않게 한다.
    env.pop("LIGHTWEIGHT_HARNESS_REF", None)

    def run(*args):
        # Bash 표준 입력으로 스크립트를 전달해 curl | bash와 같은 입력 방식을 재현한다.
        # 10초 제한은 테스트 멈춤 방지용이며 실제 설치 스크립트의 기능은 아니다.
        return subprocess.run(
            [str(commands / "bash"), "-s", "--", *args],
            input=SCRIPT.read_text(), text=True, capture_output=True, env=env,
            cwd=tmp_path, timeout=10,
        )
    return run, env, commands


def test_piped_install_and_reinstall_use_repository_source(installer):
    # 기존 uv 재사용, CLI ref 우선순위, 같은 경로에 재설치하는 동작을 함께 검증한다.
    run, env, commands = installer
    (commands / "uv").symlink_to(env["LIGHTWEIGHT_HARNESS_TEST_UV_STUB"])
    env["LIGHTWEIGHT_HARNESS_REF"] = "main"
    for _ in range(2):
        result = run("--ref", "test-commit")
        assert result.returncode == 0, result.stderr
        assert "Lightweight-Harness is installed" in result.stdout
        assert "export PATH=" in result.stdout
    calls = [json.loads(line) for line in Path(env["LIGHTWEIGHT_HARNESS_TEST_UV_LOG"]).read_text().splitlines()]
    # 전용 환경에 지정한 ref의 저장소 아카이브를 설치하는지 확인한다.
    assert len(calls) == 2
    assert calls[0]["args"][-1] == "https://github.com/highsun9941/Lightweight-Harness/archive/test-commit.tar.gz"
    assert calls[0]["tools"] == env["LIGHTWEIGHT_HARNESS_INSTALL_DIR"] + "/tools"
    assert calls[0]["python"] == env["LIGHTWEIGHT_HARNESS_INSTALL_DIR"] + "/python"
    assert "--managed-python" in calls[0]["args"]
    assert "--force" not in calls[0]["args"]
    assert not Path(env["LIGHTWEIGHT_HARNESS_TEST_CURL_LOG"]).exists()


def test_bootstraps_uv_without_python_or_git_on_path(installer):
    # uv·Python·Git이 PATH에 없어도 uv 준비부터 시작할 수 있어야 한다.
    run, env, commands = installer
    assert not any((commands / name).exists() for name in ("uv", "python", "python3", "git"))
    result = run()
    assert result.returncode == 0, result.stderr
    assert (Path(env["LIGHTWEIGHT_HARNESS_INSTALL_DIR"]) / "uv/uv").exists()
    args = json.loads(Path(env["LIGHTWEIGHT_HARNESS_TEST_CURL_LOG"]).read_text())
    assert "https://astral.sh/uv/install.sh" in args
    assert not Path(args[args.index("-o") + 1]).parent.exists()
    # 두 번째 curl을 의도적으로 실패하게 해도 준비된 전용 uv를 재사용해 성공해야 한다.
    (commands / "curl").unlink()
    (commands / "curl").write_text("#!/bin/sh\nexit 99\n")
    (commands / "curl").chmod(0o755)
    assert run().returncode == 0


def test_failed_download_is_never_executed(installer):
    # curl 실패 시 내려받은 내용을 실행하지 않고 임시 파일도 정리하는지 확인한다.
    run, env, _ = installer
    env["LIGHTWEIGHT_HARNESS_TEST_FAIL_DOWNLOAD"] = "1"
    result = run()
    assert result.returncode != 0
    assert "Could not download uv" in result.stderr
    assert "Lightweight-Harness is installed" not in result.stdout
    assert not Path(env["LIGHTWEIGHT_HARNESS_TEST_BAD_DOWNLOAD_MARKER"]).exists()
    assert not Path(env["LIGHTWEIGHT_HARNESS_TEST_UV_LOG"]).exists()
    args = json.loads(Path(env["LIGHTWEIGHT_HARNESS_TEST_CURL_LOG"]).read_text())
    assert not Path(args[args.index("-o") + 1]).parent.exists()


def test_failed_install_preserves_existing_command(installer):
    # uv 실패 시 기존 lightweight-harness 내용을 보존하고 성공 메시지를 표시하지 않는지 확인한다.
    run, env, commands = installer
    (commands / "uv").symlink_to(env["LIGHTWEIGHT_HARNESS_TEST_UV_STUB"])
    env["LIGHTWEIGHT_HARNESS_TEST_FAIL_UV"] = "1"
    existing = Path(env["LIGHTWEIGHT_HARNESS_BIN_DIR"]) / "lightweight-harness"
    existing.parent.mkdir()
    existing.write_text("existing application")
    result = run()
    assert result.returncode != 0
    assert "Lightweight-Harness is installed" not in result.stdout
    assert existing.read_text() == "existing application"


@pytest.mark.parametrize("args", [("--ref",), ("--ref", "../other"), ("--unknown",)])
def test_bad_arguments_fail_before_installing(installer, args):
    # 인자 누락·잘못된 ref·알 수 없는 옵션은 다운로드와 uv 실행 전에 거절해야 한다.
    run, env, _ = installer
    assert run(*args).returncode != 0
    assert not Path(env["LIGHTWEIGHT_HARNESS_TEST_UV_LOG"]).exists()
    assert not Path(env["LIGHTWEIGHT_HARNESS_TEST_CURL_LOG"]).exists()


def test_help_needs_no_network_or_runtime(installer):
    # curl 없이도 도움말을 확인할 수 있고 설치 디렉터리도 만들지 않는지 검증한다.
    run, env, commands = installer
    (commands / "curl").unlink()
    assert run("--help").returncode == 0
    assert not Path(env["LIGHTWEIGHT_HARNESS_INSTALL_DIR"]).exists()
