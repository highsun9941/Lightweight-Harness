# Lightweight-Harness

[![English](https://img.shields.io/badge/English-555555?style=for-the-badge)](README.md) [![한국어](https://img.shields.io/badge/%ED%95%9C%EA%B5%AD%EC%96%B4-0969DA?style=for-the-badge)](README.ko.md)

> **모델이 판단하고, 런타임은 실행합니다.**

시간이 지날수록 LLM은 더 똑똑해집니다. 우리는 모델을 둘러싼 하네스가 계속 커지기보다, 오히려 가벼워져야 한다고 생각합니다. 모델과 API 제공자가 가진 기본 지침과 도구 사용 능력 위에 과도한 시스템 프롬프트와 고정된 작업 절차를 덧붙이면, 모델의 판단을 방해하고 성능을 떨어뜨릴 수 있기 때문입니다.

Lightweight-Harness는 모델에게 **셸 실행 도구 `run_command` 하나만** 기본으로 노출합니다. 파일 읽기·검색·수정과 테스트도 모델이 셸 명령으로 수행합니다. 사용자의 입력, 현재 세션의 대화와 도구 결과를 전달하며, 자체 시스템 프롬프트나 저장소 지침을 자동으로 주입하지 않습니다. 계획, 실행 순서, 문제 진단과 재시도는 모델이 결정합니다.

CC Switch처럼 여러 API 제공자를 프로필로 등록하고 필요할 때 선택할 수 있습니다. 하네스, 장기 메모리, 컨텍스트 압축, 스킬, 추가 도구 등의 기능은 사용자가 원하는 것만 커뮤니티 플러그인으로 조립하는 생태계를 지향합니다. 현재는 이를 위한 작은 플러그인 진입점을 제공하며, 기본 활성 플러그인은 없습니다.

**내장 안전장치는 없습니다. Docker 환경에서 사용하는 것을 권장합니다.** 파일 수정과 셸 명령은 별도 승인 없이 프로세스의 권한으로 실행됩니다.

## 설치

Linux, macOS, WSL에서는 한 줄로 설치할 수 있습니다.

```bash
# 이 저장소의 설치 스크립트로 전용 Python 환경과 lightweight-harness 실행 명령을 준비한다.
curl -fsSL https://raw.githubusercontent.com/highsun9941/Lightweight-Harness/main/install.sh | bash
```

설치 스크립트가 필요한 경우 [uv](https://docs.astral.sh/uv/)와 Python 3.12를 준비하고, 이 저장소의 `main` 코드를 독립된 Python 환경에 설치합니다. Python이나 Git을 미리 설치할 필요가 없고 `sudo`도 사용하지 않습니다. 설치 후 `lightweight-harness`를 실행하세요. `~/.local/bin`이 PATH에 없으면 설치 완료 메시지에 나온 설정을 적용합니다.

```bash
# 사용자 영역에 설치한 명령을 현재 셸에서 찾을 수 있게 한다.
export PATH="$HOME/.local/bin:$PATH"
lightweight-harness
```

같은 설치 명령을 다시 실행하면 업데이트됩니다. 기본 설치 경로는 `~/.local/share/lightweight-harness`, 실행 명령은 `~/.local/bin/lightweight-harness`입니다. 제공자 설정과 셸 설정 파일은 자동으로 바꾸지 않습니다. 기존의 다른 `lightweight-harness` 명령과 충돌하면 설치를 중단하고 안내합니다.

스크립트를 먼저 확인하거나 특정 태그·커밋을 설치하려면:

```bash
# 스크립트를 파일로 받아 설치 동작과 지원 옵션을 먼저 검토한다.
curl -fsSL https://raw.githubusercontent.com/highsun9941/Lightweight-Harness/main/install.sh -o install.sh
less install.sh
bash install.sh --help
# 기본 main 대신 원하는 Git ref를 지정할 수 있습니다.
bash install.sh --ref main
```

설치 위치는 `LIGHTWEIGHT_HARNESS_INSTALL_DIR`, 실행 명령 위치는 `LIGHTWEIGHT_HARNESS_BIN_DIR`로 지정할 수 있습니다. 두 경로는 절대 경로여야 하며 재설치할 때도 같은 값을 사용하세요. Git ref는 `LIGHTWEIGHT_HARNESS_REF`로도 지정할 수 있습니다. 파이프 명령에서 환경변수는 `bash` 쪽에 전달합니다.

```bash
# 파이프 오른쪽의 bash가 읽도록 ref 환경변수를 지정한다.
curl -fsSL https://raw.githubusercontent.com/highsun9941/Lightweight-Harness/main/install.sh | LIGHTWEIGHT_HARNESS_REF=main bash
```

Python 3.12 이상과 pipx가 이미 있다면 직접 설치할 수도 있습니다.

```bash
# 저장소 소스를 pipx의 격리된 환경에 설치한다.
pipx install 'git+https://github.com/highsun9941/Lightweight-Harness.git'
```

개발용 소스 설치:

```bash
# 로컬 수정이 실행에 반영되는 개발 환경을 준비한다.
git clone https://github.com/highsun9941/Lightweight-Harness.git
cd Lightweight-Harness
# 시스템 Python 패키지와 분리한 뒤 editable 설치로 소스 변경을 바로 사용한다.
python -m venv .venv
source .venv/bin/activate
pip install -e .
lightweight-harness
```

실행한 디렉터리가 작업 디렉터리입니다. 소스 설치 환경에서는 `python -m lightweight_harness`도 같은 UI를 실행합니다.

기존 설치를 업데이트할 때는 재설치한 뒤 제공자 설정을 `~/.config/lightweight-harness/config.toml`에 두거나, `--config`로 현재 설정 파일을 지정하세요. 프로젝트 전용 환경변수는 이제 `LIGHTWEIGHT_HARNESS_` 접두사를 사용합니다.

## 기본 동작

기본 모델 요청에는 사용자 대화, 이전 모델 응답, 도구 결과와 `run_command` 하나만 들어갑니다.

| 도구 | 동작 |
| --- | --- |
| `run_command` | 셸 명령 실행 및 종료 코드·출력 반환 |

파일 읽기·검색·수정, 프로그램 실행과 테스트는 모두 이 도구를 통해 셸 명령으로 수행합니다. 별도의 내장 파일 도구는 없습니다.

모델 응답 → 도구 호출 실행 → 결과 전달을 반복하며, 모델이 도구 호출 없이 응답하면 해당 턴을 마칩니다. 셸 명령은 현재 작업 디렉터리에서 시작하며, 파일 접근은 이 디렉터리 안으로 제한되지 않습니다.

- 자체 system/developer 프롬프트가 없습니다.
- `AGENTS.md`, 메모리, 스킬, 저장소 지도 등을 자동으로 읽어 넣지 않습니다. 모델은 필요하면 셸 명령으로 직접 읽을 수 있습니다.
- 자동 계획, 모델 라우팅, 숨겨진 재시도, 컨텍스트 요약·압축이 없습니다.
- 대화는 현재 프로세스 안에서 유지됩니다. 기본 상태에서는 저장하거나 다음 실행에 복원하지 않습니다.
- 컨텍스트 한도와 API 오류는 그대로 표시합니다. 도구 실행 오류는 모델에 결과로 돌려주며, 이후 행동은 모델이 정합니다.
- UI는 긴 도구 출력을 짧게 표시하지만, 모델에는 전체 결과를 전달합니다.

## API 제공자 프로필

`~/.config/lightweight-harness/config.toml`에 프로필을 등록합니다. 다른 파일은 `--config` 또는 `LIGHTWEIGHT_HARNESS_CONFIG`로 지정할 수 있습니다.

```toml
# CLI나 환경변수로 다른 제공자를 선택하지 않았을 때 사용할 프로필이다.
default_provider = "openrouter"

[plugins]
# 기본 코어만 사용한다. 선택형 확장은 module:setup 형태로 직접 추가한다.
enabled = []

[providers.openrouter]
# name은 화면 표시용, base_url은 전송 계층이 API 경로를 붙일 루트 주소다.
name = "OpenRouter"
base_url = "https://openrouter.ai/api/v1"
# 키 자체를 저장하지 않고 이 환경변수에서 요청 시 읽는다.
api_key_env = "OPENROUTER_API_KEY"
model = "openai/gpt-5"

[providers.deepseek]
# 같은 OpenAI 호환 전송을 주소와 모델 설정만 바꿔 사용할 수 있다.
name = "DeepSeek"
base_url = "https://api.deepseek.com/v1"
api_key_env = "DEEPSEEK_API_KEY"
model = "deepseek-chat"

[providers.anthropic]
# 이 프로필은 요청·응답을 Anthropic Messages 형식으로 변환한다.
name = "Anthropic"
api_format = "anthropic"
base_url = "https://api.anthropic.com/v1"
api_key_env = "ANTHROPIC_API_KEY"
model = "your-claude-model" # 계정에서 사용할 모델 ID로 변경
max_tokens = 4096 # 한 응답의 최대 출력 토큰 수

[providers.local]
name = "Local"
base_url = "http://localhost:1234/v1"
api_key_env = "" # 인증이 없는 로컬 서버에만 사용
model = "your-local-model" # 서버에 로드한 모델 ID로 변경
```

`api_format = "openai"`가 기본값이며, OpenAI 호환 **Chat Completions** API와 도구 호출을 지원하는 서버에 연결합니다. `anthropic`은 기본 **Messages** API 형식을 사용합니다. `base_url`에는 API 루트 경로를 넣으세요. 런타임이 각각 `/chat/completions`, `/messages`를 붙입니다. `max_tokens`는 Anthropic 요청의 최대 출력 토큰 수입니다.

```bash
# 프로필이 참조하는 키를 현재 셸에 설정하고 사용할 제공자를 선택한다.
export OPENROUTER_API_KEY=...
lightweight-harness --provider openrouter
# 다른 설정 파일과 모델 재정의는 이번 실행에만 적용된다.
lightweight-harness --config /path/to/config.toml --provider anthropic --model YOUR_MODEL_ID
```

제공자 선택 우선순위는 `--provider` → `LIGHTWEIGHT_HARNESS_PROVIDER` → `default_provider` → 이름순 첫 프로필입니다. 모델은 `--model` → `LIGHTWEIGHT_HARNESS_MODEL` → 프로필의 `model` 순으로 선택합니다. 키는 `api_key_env`가 가리키는 환경변수에서 읽습니다.

기존 환경변수 단축 설정도 지원합니다. `OPENAI_API_KEY` 또는 `LIGHTWEIGHT_HARNESS_API_KEY`는 `openai` 프로필을, `OPENROUTER_API_KEY`는 `openrouter` 프로필을 만듭니다. OpenAI 호환 기본 주소는 `OPENAI_BASE_URL`로 바꿀 수 있고, TOML의 같은 이름 프로필이 단축 설정을 덮어씁니다.

UI 명령:

| 명령 | 동작 |
| --- | --- |
| `/help` | 도움말 |
| `/providers` 또는 `/models` | 설정된 제공자와 모델 확인 |
| `/use <provider> [model]` | 제공자 선택 및 새 세션 시작 |
| `/plugins` | 현재 활성 플러그인 확인 |
| `/clear` | 현재 제공자로 새 세션 시작 |
| `/quit` | 종료 |

제공자를 바꾸면 이전 대화를 새 제공자에게 전송하지 않습니다. `/use`는 현재 실행에 적용되며 다음 실행의 기본값은 설정 파일로 정합니다. 작업 중에는 새 요청과 세션 변경을 받지 않습니다. `/quit`은 실행 중인 셸 프로세스를 종료하는 기능이 아닙니다.

## 선택형 플러그인

기본값은 빈 목록입니다. 플러그인 패키지를 같은 Python 환경에 설치한 다음, Python 모듈의 `setup(agent)` 진입점을 명시합니다.

```toml
[plugins]
# 설치된 모듈의 setup 함수를 새 Agent 초기화 시 호출한다.
enabled = ["my_plugin:setup"]
```

```bash
# 설정 목록 뒤에 플러그인 하나를 추가한다.
lightweight-harness --plugin my_plugin:setup
# 설정 파일과 CLI에서 선택한 플러그인을 모두 끄는 별도의 실행 예제다.
lightweight-harness --no-plugins
```

설정 목록 뒤에 `--plugin` 목록이 순서대로 추가되고, 중복 진입점은 한 번만 실행됩니다. `--no-plugins`는 두 목록을 모두 무시합니다. 플러그인 자동 검색·자동 설치는 없습니다.

플러그인은 추가 도구 등록, 요청 전 대화 처리, 이벤트 구독을 통해 필요한 하네스·메모리·압축·스킬 로딩을 구현할 수 있습니다. 명시적으로 선택한 플러그인은 기본 도구 목록과 프롬프트를 바꿀 수 있습니다. 플러그인은 CLI와 같은 권한의 Python 코드입니다.

[플러그인 작성 안내](docs/plugins.md)와 [세션 로그 예제](examples/plugins/session_log.py)를 제공합니다. 커뮤니티 패키지 목록, 배포·설치 도구, 버전 호환성 규약은 앞으로 발전시킬 영역입니다.

## Docker에서 실행하기

```bash
# Python·Git·ripgrep과 CLI를 포함한 이미지를 만든다.
docker build -t lightweight-harness .
# 호스트 UID/GID로 파일 소유권을 맞추고 작업 디렉터리·필요한 환경변수를 연결한다.
docker run --rm -it \
  --user "$(id -u):$(id -g)" \
  --cap-drop ALL --security-opt no-new-privileges \
  -v "$PWD:/workspace" \
  -e OPENROUTER_API_KEY \
  -e LIGHTWEIGHT_HARNESS_PROVIDER=openrouter \
  -e LIGHTWEIGHT_HARNESS_MODEL=openai/gpt-5 \
  lightweight-harness
```

Linux에서 `--user`에 호스트 UID/GID를 지정하면 마운트한 작업 파일의 쓰기 권한을 맞출 수 있습니다. 이미지에는 Python, Git, ripgrep이 포함됩니다. 프로젝트에 필요한 다른 런타임은 이미지에 추가하세요.

설정 파일과 사용자 정의 제공자를 쓰려면:

```bash
# 설정 파일은 읽기 전용으로 연결하고 컨테이너 안 경로를 CLI에 알려 준다.
docker run --rm -it \
  --user "$(id -u):$(id -g)" \
  --cap-drop ALL --security-opt no-new-privileges \
  -v "$PWD:/workspace" \
  -v "$HOME/.config/lightweight-harness/config.toml:/tmp/lightweight-harness-config.toml:ro" \
  -e LIGHTWEIGHT_HARNESS_CONFIG=/tmp/lightweight-harness-config.toml \
  -e ANTHROPIC_API_KEY \
  lightweight-harness --provider anthropic
```

Compose의 기본 작업 경로는 이 저장소입니다.

```bash
# Compose에서도 호스트 파일 소유권을 맞추며 현재 소스로 이미지를 다시 빌드한다.
LIGHTWEIGHT_HARNESS_UID="$(id -u)" LIGHTWEIGHT_HARNESS_GID="$(id -g)" docker compose run --rm --build lightweight-harness
```

Docker는 실행 환경을 분리하지만, 쓰기 가능하게 마운트한 파일과 전달한 키에는 여전히 접근할 수 있습니다. 작업용 디렉터리와 필요한 키만 전달하세요. 컨테이너 안의 `localhost`는 컨테이너 자신을 가리키므로, 호스트의 로컬 모델 서버를 쓸 때는 환경에 맞는 호스트 주소를 설정해야 합니다.

## 저장소 구조

현재 저장소에서 실행·설치·설정·검증에 사용하는 파일과 각 역할입니다.

```text
Lightweight-Harness/
├── lightweight_harness/      # CLI 실행 코어
│   ├── __init__.py           # 패키지 버전
│   ├── __main__.py           # python -m lightweight_harness 실행 진입점
│   ├── app.py                # CLI 옵션 처리, 설정 로딩, UI 시작
│   ├── tui.py                # 터미널 UI, 사용자 명령, 제공자·세션 전환
│   ├── agent.py              # 모델 요청 → 도구 실행 → 결과 전달 반복
│   ├── tools.py              # 유일한 기본 도구 run_command 정의와 실행
│   ├── providers.py          # TOML·환경변수에서 API 제공자와 모델 선택
│   ├── transport.py          # OpenAI 호환·Anthropic API 요청과 응답 변환
│   └── plugins.py            # 명시적으로 선택한 module:setup 플러그인 로딩
├── examples/                 # 사용자가 적용할 수 있는 설정·플러그인 예제
│   ├── config.toml           # API 제공자 프로필과 플러그인 설정 예제
│   └── plugins/
│       └── session_log.py    # 완료된 대화를 JSONL로 저장하는 선택형 플러그인
├── docs/
│   └── plugins.md            # 플러그인 작성법, 확장 API, 실행 예제
├── tests/                    # 실제 API 키 없이 실행하는 자동 테스트
│   ├── conftest.py           # 테스트를 개인 설정·인증 환경변수에서 격리
│   ├── test_agent.py         # 모델·도구 반복, 오류 반환, 플러그인 선택 검증
│   ├── test_tools.py         # 셸 파일 작업, 종료 코드·출력, 제거된 도구 검증
│   ├── test_transport.py     # OpenAI·Anthropic 요청과 도구 호출 왕복 검증
│   ├── test_providers.py     # 제공자 설정, 선택 우선순위, 인증 설정 검증
│   ├── test_config.py        # CLI 옵션과 설정·플러그인 선택 전달 검증
│   ├── test_tui.py           # UI의 제공자·세션 전환과 중복 요청 처리 검증
│   └── test_installer.py     # 설치·재설치, uv 준비, 설치 실패 처리 검증
├── .github/workflows/
│   └── ci.yml                # 테스트와 Linux·macOS 설치·재설치 CI
├── install.sh                # curl 설치 진입점, uv·Python 준비와 설치·업데이트
├── pyproject.toml            # 패키지 정보, 의존성, lightweight-harness 명령 등록
├── lightweight_harness.py    # python lightweight_harness.py 직접 실행 진입점
├── Dockerfile                # Python·Git·ripgrep을 포함한 실행 이미지
├── docker-compose.yml        # 작업 디렉터리·환경변수를 연결하는 컨테이너 설정
├── .dockerignore             # Docker 빌드 컨텍스트에서 제외할 파일
├── .gitignore                # Git에서 제외할 가상환경·캐시·로컬 환경 파일
├── README.md                 # 영어 안내: 프로젝트 방향, 설치법, 사용법, 저장소 구조
└── README.ko.md              # 한국어 안내: 프로젝트 방향, 설치법, 사용법, 저장소 구조
```

`lightweight-harness`와 `python -m lightweight_harness`는 모두 `app.py`의 `main()`으로 진입합니다. `tui.py`가 사용자 입력을 받아 `agent.py`에 전달하고, 에이전트는 `transport.py`로 모델과 통신하며 `tools.py`로 셸 명령을 실행합니다. `examples/`의 설정과 플러그인은 사용자가 직접 지정해 사용할 수 있습니다.

## 개발 및 검증

```bash
# 테스트 도구를 포함해 설치하고 Python 문법·자동 테스트·CLI 진입점을 차례로 확인한다.
pip install -e '.[dev]'
python -m compileall -q lightweight_harness
pytest -q
python -m lightweight_harness --help
```

테스트는 모의 HTTP 전송을 사용해 기본 프롬프트 부재, `run_command` 단일 도구 노출, 도구 오류 반환, 제공자 프로필 선택, OpenAI/Anthropic 도구 호출 왕복, 플러그인 선택과 UI 세션 전환을 검증합니다. 셸을 통한 파일 작업과 종료 코드·표준 출력·표준 오류 반환도 확인합니다. 실제 API 호출이나 API 키가 필요하지 않습니다.

초기 실험 프로젝트입니다. 작은 코어와 선택형 확장을 분리하는 것이 개발 방향입니다.
