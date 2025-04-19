import os
import json
import logging
from typing import Dict, Any, List, Optional
from common.llm_client import LLMClient  # 프로젝트 공통 LLM 클라이언트 임포트

class BrokerLLMClient:
    def __init__(self, default_model: str = "gpt-4o-mini"):
        self.llm_client = LLMClient(default_model=default_model)
        self.logger = logging.getLogger("broker_llm_client")
    
    async def infer_missing_params(self, task_description: str, 
                                  missing_params: List[Dict[str, Any]], 
                                  existing_params: Dict[str, Any]) -> Dict[str, Any]:
        """누락된 파라미터 추론"""
        prompt = self._build_param_inference_prompt(
            task_description, missing_params, existing_params
        )
        
        try:
            response = await self.llm_client.generate(prompt, response_format={"type": "json"})
            # JSON 파싱 및 결과 반환
            result = json.loads(response)
            self.logger.info(f"파라미터 추론 결과: {result}")
            return result
        except Exception as e:
            self.logger.error(f"파라미터 추론 실패: {str(e)}")
            return {}
    
    def _build_param_inference_prompt(self, task_description: str, 
                                     missing_params: List[Dict[str, Any]], 
                                     existing_params: Dict[str, Any]) -> str:
        """파라미터 추론을 위한 프롬프트 생성"""
        # 타입별 예시 값 제공 (파라미터 타입 이해를 돕기 위함)
        type_examples = {
            "string": "텍스트 값 (예: '검색어', '보고서', '한국어')",
            "number": "숫자 값 (예: 5, 100, 0.5)",
            "boolean": "불리언 값 (true 또는 false)",
            "array": "배열 값 (예: ['항목1', '항목2'])",
            "object": "객체 값 (예: {'키1': '값1', '키2': '값2'})"
        }
        
        # 파라미터 설명에 타입 예시 추가
        param_descriptions = []
        for p in missing_params:
            type_info = p.get('type', 'string')
            type_example = type_examples.get(type_info, "")
            enum_values = p.get('enum')
            enum_info = f", 허용값: {enum_values}" if enum_values else ""
            
            param_desc = (
                f"- {p['name']}: {p['description']}\n"
                f"  타입: {type_info} {type_example}{enum_info}\n"
                f"  필수: {p['required']}"
            )
            
            # 기본값 정보 추가
            if 'default' in p and p['default'] is not None:
                param_desc += f"\n  기본값: {p['default']}"
                
            param_descriptions.append(param_desc)
        
        # 기존 파라미터 표시
        existing_param_section = ""
        if existing_params:
            existing_items = []
            for k, v in existing_params.items():
                if isinstance(v, str):
                    item = f"- {k}: \"{v}\""
                else:
                    item = f"- {k}: {v}"
                existing_items.append(item)
            existing_param_section = "현재 제공된 파라미터:\n" + "\n".join(existing_items)
        else:
            existing_param_section = "현재 제공된 파라미터: 없음"
        
        # 최종 프롬프트 구성
        prompt = f"""# 파라미터 추론 작업

당신은 에이전트 시스템의 파라미터 추론 전문가입니다. 사용자의 태스크를 분석하고 제공되지 않은 필수 파라미터를 추론해 주세요.

## 태스크 설명
{task_description}

## {existing_param_section}

## 추론이 필요한 파라미터
{chr(10).join(param_descriptions)}

## 지침
1. 태스크 설명과 현재 제공된 파라미터를 기반으로 가장 적절한 파라미터 값을 추론하세요.
2. 각 파라미터의 타입과 설명에 맞는 값을 생성하세요.
3. 값을 확신할 수 없는 경우 가장 합리적인 가정을 하세요.
4. 열거형(enum) 값이 있는 경우, 반드시 해당 값 중에서만 선택하세요.

다음 JSON 형식으로만 응답하세요:
{{
  "파라미터명1": 값1,
  "파라미터명2": 값2,
  ...
}}

참고: 문자열은 따옴표로 감싸고, 숫자/불리언/배열은 그대로 표현하세요.
"""
        return prompt 