"""선택형 예제: 완료된 턴의 대화 전체를 작업 디렉터리의 JSONL 파일에 저장한다."""
import json
from pathlib import Path


def setup(agent):
    # 세션 생성 시 콜백만 등록한다. 기본 프롬프트·도구를 변경하거나 과거 기록을 복원하지 않는다.
    def on_event(event):
        # 도구 호출이 끝나 최종 응답까지 받은 턴만 기록한다. 요청 실패 시에는 이 이벤트가 없다.
        if event.kind == "turn_end":
            # 매 턴의 전체 대화를 한 줄씩 덧붙인다. 증분 로그가 아니므로 이전 대화도 반복 기록된다.
            # 사용자 입력과 도구 출력이 그대로 저장되므로 기록이 필요한 경우에만 활성화한다.
            with Path("lightweight-harness-session.jsonl").open("a", encoding="utf-8") as output:
                # 한글을 이스케이프하지 않아 사람이 읽을 수 있게 하고 개행으로 레코드를 구분한다.
                output.write(json.dumps(agent.messages, ensure_ascii=False) + "\n")

    # 코어 이벤트를 구독하므로 별도의 모델 요청이나 실행 루프가 필요하지 않다.
    agent.event_handlers.append(on_event)
