# 패키지의 최소 Python 버전을 맞추고 불필요한 기본 도구가 적은 이미지를 사용한다.
FROM python:3.12-slim

# 셸 도구가 시작할 작업 위치이며 사용자가 프로젝트를 마운트할 경로다.
WORKDIR /workspace

# 기본 실행 사용자를 root와 분리한다. Compose에서는 호스트 UID/GID로 재정의할 수 있다.
RUN useradd --create-home --uid 10001 lightweight-harness
# 소스 관리와 텍스트 검색에 쓸 도구를 제공하고 설치 목록 캐시는 같은 레이어에서 지운다.
RUN apt-get update && apt-get install -y --no-install-recommends git ripgrep \
    && rm -rf /var/lib/apt/lists/*

# 패키징에 필요한 파일만 임시 경로에 복사해 설치하고 /workspace는 작업 공간으로 남긴다.
COPY pyproject.toml README.md /tmp/
COPY lightweight_harness /tmp/lightweight_harness
RUN pip install --no-cache-dir /tmp

# 컨테이너 실행 시에는 일반 사용자로 lightweight-harness를 시작한다. 뒤에 붙인 인자는 CLI에 전달된다.
USER lightweight-harness
ENTRYPOINT ["lightweight-harness"]
