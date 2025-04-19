from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel
from .registry_client import AgentParam
import logging
import json

class ParamSchema(BaseModel):
    name: str
    description: str
    required: bool = False
    type: str = "string"
    default: Optional[Any] = None

class ParamProcessor:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.logger = logging.getLogger("param_processor")
        
    def validate_params(self, params: Dict[str, Any], param_schemas: List[AgentParam]) -> Dict[str, Any]:
        """파라미터 유효성 검증 및 타입 변환"""
        result = params.copy()
        
        for schema in param_schemas:
            # 파라미터가 없고 필수인 경우 기본값 사용
            if schema.name not in result:
                if schema.required and schema.default is not None:
                    result[schema.name] = schema.default
                continue
                
            # 타입 변환 및 검증
            value = result[schema.name]
            param_type = schema.type.lower()
            
            try:
                # 타입별 변환 및 검증
                if param_type == "string":
                    result[schema.name] = str(value)
                    
                elif param_type == "number":
                    if isinstance(value, str) and value.strip():
                        # 문자열을 숫자로 변환 시도
                        try:
                            if '.' in value:
                                result[schema.name] = float(value)
                            else:
                                result[schema.name] = int(value)
                        except ValueError:
                            self.logger.warning(f"숫자 변환 실패: {value}, 기본값 사용")
                            result[schema.name] = schema.default if schema.default is not None else 0
                    elif isinstance(value, (int, float)):
                        # 이미 숫자면 그대로 사용
                        pass
                    else:
                        # 변환 불가능하면 기본값 사용
                        self.logger.warning(f"숫자 변환 불가: {value}, 기본값 사용")
                        result[schema.name] = schema.default if schema.default is not None else 0
                        
                elif param_type == "boolean":
                    if isinstance(value, str):
                        result[schema.name] = value.lower() in ('true', 'yes', '1', 'y')
                    else:
                        result[schema.name] = bool(value)
                        
                elif param_type == "array":
                    if isinstance(value, str):
                        try:
                            # 문자열을 배열로 변환 시도
                            parsed = json.loads(value)
                            if isinstance(parsed, list):
                                result[schema.name] = parsed
                            else:
                                result[schema.name] = [value]
                        except json.JSONDecodeError:
                            # 쉼표로 구분된 문자열이라고 가정하고 분할
                            result[schema.name] = [item.strip() for item in value.split(",")]
                    elif not isinstance(value, list):
                        # 리스트가 아니면 단일 항목 리스트로 변환
                        result[schema.name] = [value]
                        
                # enum 확인
                if schema.enum and result[schema.name] not in schema.enum:
                    self.logger.warning(f"유효하지 않은 enum 값: {result[schema.name]}, 기본값 사용")
                    result[schema.name] = schema.default if schema.default is not None else schema.enum[0]
                    
            except Exception as e:
                self.logger.error(f"파라미터 '{schema.name}' 변환 오류: {str(e)}")
                # 오류 시 기본값 사용
                if schema.default is not None:
                    result[schema.name] = schema.default
        
        return result
    
    async def fill_missing_params(self, params: Dict[str, Any], param_schemas: List[AgentParam], 
                                 task_description: str) -> Dict[str, Any]:
        """부족한 파라미터를 LLM을 통해 추론하여 채우기"""
        result = params.copy()
        missing_params = []
        
        for schema in param_schemas:
            if schema.name not in result and schema.required:
                missing_params.append(schema)
        
        if missing_params and self.llm_client:
            self.logger.info(f"추론이 필요한 파라미터: {[p.name for p in missing_params]}")
            # LLM을 통한 파라미터 추론 로직
            inferred_params = await self._infer_params_with_llm(missing_params, task_description, params)
            
            # 추론된 파라미터에 대한 타입 검증
            for schema in missing_params:
                if schema.name in inferred_params:
                    # 타입 검증을 위해 임시 딕셔너리 생성
                    temp_params = {schema.name: inferred_params[schema.name]}
                    validated = self.validate_params(temp_params, [schema])
                    result[schema.name] = validated[schema.name]
                    self.logger.info(f"파라미터 '{schema.name}' 추론됨: {result[schema.name]}")
                else:
                    self.logger.warning(f"파라미터 '{schema.name}' 추론 실패")
        
        return result
    
    async def _infer_params_with_llm(self, missing_params: List[AgentParam], 
                                    task_description: str, 
                                    existing_params: Dict[str, Any]) -> Dict[str, Any]:
        """LLM을 사용하여 누락된 파라미터 추론"""
        if not self.llm_client:
            return {}
            
        try:
            # missing_params를 딕셔너리 리스트로 변환
            param_dicts = [
                {
                    "name": p.name,
                    "description": p.description,
                    "type": p.type,
                    "required": p.required,
                    "default": p.default,
                    "enum": p.enum
                }
                for p in missing_params
            ]
            
            response = await self.llm_client.infer_missing_params(
                task_description, 
                param_dicts,
                existing_params
            )
            return response
        except Exception as e:
            self.logger.error(f"파라미터 추론 실패: {str(e)}")
            return {} 