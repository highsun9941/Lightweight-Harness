# python -m lightweight_harness도 설치된 lightweight-harness 명령과 동일한 CLI를 실행한다.
from .app import main

if __name__ == "__main__":
    # 정상 종료·설정 오류 등의 종료 상태를 호출한 셸에 돌려준다.
    raise SystemExit(main())
