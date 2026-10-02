"""API 형식만 변환한다. 프롬프트·라우팅·재시도·대화 관리 정책은 추가하지 않는다."""
from __future__ import annotations

import json
from typing import Any

import httpx

from .providers import ProviderConfig


def _anthropic_history(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # 코어의 OpenAI 형태 대화를 Anthropic의 메시지 블록과 별도 system 필드로 나눈다.
    history: list[dict[str, Any]] = []
    system: list[dict[str, Any]] = []
    for message in messages:
        role = message["role"]
        content = message.get("content")
        # 텍스트는 text 블록으로 감싸고 이미 블록 목록인 내용은 유지한다.
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) and content else content or []
        if role in {"system", "developer"}:
            # 플러그인이 명시적으로 넣은 지침만 옮긴다. 여기서 새 지침을 생성하지 않는다.
            system.extend(blocks)
            continue
        if role == "tool":
            # Anthropic은 도구 결과를 user 역할의 tool_result 블록으로 받는다.
            role = "user"
            blocks = [{"type": "tool_result", "tool_use_id": message["tool_call_id"],
                       "content": content, "is_error": message.get("_is_error", False)}]
        elif role == "assistant":
            if "_anthropic_content" in message:
                # 서명 등 내부 의미를 해석하지 않는 원본 블록도 후속 요청에 그대로 보존한다.
                blocks = message["_anthropic_content"]
            else:
                # 원본 블록이 없는 대화는 일반 텍스트와 코어의 도구 호출 정보로 구성한다.
                blocks = list(blocks)
                for call in message.get("tool_calls") or []:
                    blocks.append({"type": "tool_use", "id": call["id"],
                                   "name": call["function"]["name"],
                                   "input": json.loads(call["function"]["arguments"])})
        if history and history[-1]["role"] == role:
            # 연속한 도구 결과 등을 같은 역할의 메시지로 합치되 블록 순서는 유지한다.
            history[-1]["content"].extend(blocks)
        else:
            # 새 목록을 만들어 이후 병합이 코어의 원본 블록 목록을 바꾸지 않게 한다.
            history.append({"role": role, "content": list(blocks)})
    return history, system


def complete(
    client: httpx.Client,
    provider: ProviderConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    # 키 이름 해석은 프로필에 맡기고 이 함수는 선택된 API의 인증 형식만 적용한다.
    key = provider.api_key()
    headers = {"Content-Type": "application/json"}
    if provider.api_format == "anthropic":
        history, system = _anthropic_history(messages)
        # Anthropic의 버전 헤더와 인증 헤더를 사용한다.
        headers["anthropic-version"] = "2023-06-01"
        if key:
            headers["x-api-key"] = key
        body = {
            "model": provider.model,
            # Anthropic 요청에 필요한 출력 토큰 상한이며 대화 길이를 압축하는 설정은 아니다.
            "max_tokens": provider.max_tokens,
            "messages": history,
            # 코어의 동일한 도구 목록을 Anthropic의 input_schema 형식으로 바꾼다.
            "tools": [{"name": t["function"]["name"],
                       "description": t["function"]["description"],
                       "input_schema": t["function"]["parameters"]} for t in tools],
        }
        if system:
            # 기본 세션에서는 system 항목 자체를 보내지 않는다.
            body["system"] = system
        endpoint = "messages"
    else:
        if key:
            # 빈 키를 허용한 로컬 서버에는 Authorization 헤더를 보내지 않는다.
            headers["Authorization"] = f"Bearer {key}"
        body = {
            "model": provider.model,
            # 오류 표시·Anthropic 원본 등 런타임 전용 필드는 OpenAI 요청에서 제거한다.
            "messages": [{k: v for k, v in m.items() if not k.startswith("_")} for m in messages],
            "tools": tools,
            # 도구 사용 여부를 강제하지 않고 모델이 선택하도록 한다.
            "tool_choice": "auto",
        }
        endpoint = "chat/completions"
    # 제공자 주소에 맞는 경로를 붙여 단일 요청을 보낸다. 스트리밍·자동 재시도는 하지 않는다.
    response = client.post(f"{provider.base_url.rstrip('/')}/{endpoint}", headers=headers, json=body)
    # HTTP 실패를 성공 응답처럼 해석하지 않고 호출자에게 전달한다.
    response.raise_for_status()
    payload = response.json()
    if provider.api_format == "openai":
        # 코어가 쓰는 형식과 같으므로 첫 응답 메시지를 그대로 사용한다.
        return payload["choices"][0]["message"]
    blocks = payload["content"]
    # 코어가 제공자별로 분기하지 않도록 Anthropic 응답을 같은 메시지·도구 호출 형식으로 맞춘다.
    return {
        "role": "assistant",
        "content": "\n".join(block["text"] for block in blocks if block["type"] == "text"),
        "tool_calls": [{"id": block["id"], "type": "function", "function": {
            "name": block["name"], "arguments": json.dumps(block["input"]),
        }} for block in blocks if block["type"] == "tool_use"],
        # 표시용 텍스트와 별개로 다음 Anthropic 요청에 필요한 원본 전체를 유지한다.
        "_anthropic_content": blocks,
    }
