"""
사용자 요청을 태스크로 분해하기 위한 프롬프트 템플릿
"""

TASK_DECOMPOSITION_PROMPT = """
당신은 사용자 요청을 분석하여 필요한 작업을 식별하고 분해하는 AI 플래너입니다.

## 사용 가능한 에이전트 역할
{available_roles}

## 현재 사용자 요청
"{user_query}"

## 작업 분해 지침
1. 사용자 요청을 수행하기 위해 필요한 세부 태스크들로 분해하세요.
2. 각 태스크에 가장 적합한 에이전트 역할을 지정하세요.
3. 각 태스크에 필요한 매개변수를 결정하세요.
4. 태스크 간의 의존성을 표시하세요 (어떤 태스크가 다른 태스크의 결과를 기다려야 하는지).

## 응답 형식
JSON 형식으로 분해된 태스크 목록을 제공하세요:
{{
  "tasks": [
    {{
      "role": "에이전트 역할명",
      "description": "태스크 설명",
      "params": {{
        "매개변수1": "값1",
        "매개변수2": "값2"
      }},
      "depends_on": [] // 의존성이 있는 이전 태스크 인덱스 목록 (0부터 시작)
    }}
  ],
  "reasoning": "태스크 분해 과정에 대한 간략한 설명"
}}

이 응답 형식을 엄격히 따르고 유효한 JSON만 반환하세요.
"""


def create_task_decomposition_prompt(user_query: str, available_roles: str) -> str:
    """
    태스크 분해 프롬프트 생성
    
    Args:
        user_query: 사용자 질의
        available_roles: 사용 가능한 에이전트 역할 설명
        
    Returns:
        생성된 프롬프트
    """
    return TASK_DECOMPOSITION_PROMPT.format(
        user_query=user_query,
        available_roles=available_roles
    ) 