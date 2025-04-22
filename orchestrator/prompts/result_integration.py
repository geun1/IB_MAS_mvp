"""
태스크 결과를 통합하기 위한 프롬프트 템플릿
"""

RESULT_INTEGRATION_PROMPT = """
당신은 여러 AI 에이전트가 수행한 태스크 결과를 통합하여 사용자의 원래 요청에 대한 응답을 생성하는 전문가입니다.

## 원래 사용자 요청
"{original_query}"

## 수행된 태스크 및 결과
{tasks_results}

## 통합 지침
1. 모든 태스크 결과를 고려하여 원래 사용자 요청에 응답하는 일관된 답변을 생성하세요.
2. 각 에이전트가 제공한 정보를 자연스럽게 통합하세요.
3. 정보가 충돌하는 경우, 가장 신뢰할 수 있는 소스를 우선시하세요.
4. 태스크 중 일부가 실패했다면, 가능한 한 성공한 태스크 결과만으로 응답을 생성하세요.
5. 응답은 명확하고 요점을 잘 전달해야 합니다.

## 응답 형식
사용자의 원래 질문이나 요청에 직접 답하는 형식으로 통합된 응답을 작성하세요.
"""

def create_result_integration_prompt(original_query: str, tasks_results: str) -> str:
    """
    결과 통합 프롬프트 생성
    
    Args:
        original_query: 원래 사용자 질의
        tasks_results: 태스크 결과 문자열
        
    Returns:
        생성된 프롬프트
    """
    return RESULT_INTEGRATION_PROMPT.format(
        original_query=original_query,
        tasks_results=tasks_results
    ) 