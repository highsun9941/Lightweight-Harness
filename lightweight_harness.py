# 기존의 파일 직접 실행 방식도 패키지의 CLI와 같은 경로를 사용하게 한다.
from lightweight_harness.app import main

# import만 했을 때 UI가 뜨지 않도록 직접 실행한 경우에만 진입한다.
if __name__ == "__main__":
    # main의 반환값을 셸 종료 코드로 전달한다.
    raise SystemExit(main())
