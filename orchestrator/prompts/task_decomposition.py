"""
사용자 요청을 태스크로 분해하기 위한 프롬프트 템플릿
"""

TASK_DECOMPOSITION_PROMPT = """
당신은 사용자 요청을 분석하여 필요한 작업을 식별하고 분해하는 AI 플래너입니다.

## 사용 가능한 에이전트 역할 (기본 정보)
{available_roles}

{agents_detail}

## 현재 사용자 요청
"{user_query}"

## 작업 분해 지침
1. 사용자 요청을 수행하기 위해 필요한 세부 태스크들로 분해하세요.
2. 각 태스크에 가장 적합한 에이전트 역할을 지정하세요.
3. 사용 가능한 에이전트를 최대한 활용하여 태스크를 분배하세요.
4. 각 에이전트의 특성과 장점을 고려하여 가장 적합한 에이전트에게 태스크를 할당하세요.
5. 각 태스크에 필요한 매개변수를 에이전트 정의에 맞게 정확히 지정하세요.
6. 태스크 간의 의존성을 표시하세요 (어떤 태스크가 다른 태스크의 결과를 기다려야 하는지).
7. 특히 주의: 등록된 에이전트가 처리할 수 있는 모든 영역에서 에이전트를 활용하세요. 직관적으로 보이는 태스크도 해당 에이전트에게 할당하세요.

## 에이전트 활용을 위한 전략적 고려사항
1. **다양성 활용**: 다양한 역할의 에이전트를 조합하여 더 효과적인 결과를 도출하세요.
2. **적절한 순서**: 데이터를 수집하는 에이전트는 먼저, 분석이나 응답을 생성하는 에이전트는 나중에 배치하세요.
3. **특화된 기능 활용**: 각 에이전트가 가진 특화된 기능을 최대한 활용하세요.
4. **확장 가능성**: 업무를 더 작은 단위로 나누어 여러 에이전트가 병렬로 처리할 수 있게 하세요.

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


def create_task_decomposition_prompt(user_query: str, available_roles: str, agents_detail: str = None) -> str:
    """
    태스크 분해 프롬프트 생성
    
    Args:
        user_query: 사용자 질의
        available_roles: 사용 가능한 에이전트 역할 설명
        agents_detail: 에이전트 상세 정보 (선택적)
        
    Returns:
        생성된 프롬프트
    """
    # 에이전트 상세 정보가 있으면 추가
    agents_detail_section = f"""
## 에이전트 상세 정보
{agents_detail}
""" if agents_detail else ""
    
    return TASK_DECOMPOSITION_PROMPT.format(
        user_query=user_query,
        available_roles=available_roles,
        agents_detail=agents_detail_section
    ) 