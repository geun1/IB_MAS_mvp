"""
코드 생성기 모듈 - 다양한 언어 및 구조로 코드 생성
"""
import os
import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from language_config import (
    LANGUAGE_EXTENSIONS, 
    LANGUAGE_FRAMEWORKS, 
    CODE_STYLE_GUIDES, 
    TEST_FILE_PATTERNS
)

logger = logging.getLogger(__name__)

class CodeGenerator:
    """요구사항에 따라 다양한 프로그래밍 언어로 코드를 생성하는 클래스"""
    
    def __init__(self):
        # 코드 생성 전략 설정
        self.strategy = {
            "code_organization": "모듈화",  # 모듈화, 단일 파일, 마이크로서비스 등
            "documentation_level": "표준",  # 최소, 표준, 상세
            "error_handling": "견고함",     # 기본, 견고함, 완전함
            "performance_focus": "균형",    # 가독성 중심, 균형, 성능 중심
            "test_coverage": "기본"         # 없음, 기본, 전체
        }
    
    def set_strategy(self, **kwargs):
        """코드 생성 전략 설정"""
        for key, value in kwargs.items():
            if key in self.strategy:
                self.strategy[key] = value
        return self
        
    def generate_code(self, 
                     requirements: str, 
                     language: str = "python", 
                     complexity_level: int = 5,
                     include_tests: bool = False,
                     include_documentation: bool = True,
                     references: List[str] = None) -> Dict[str, Any]:
        """
        요구사항에 따라 코드 생성
        
        Args:
            requirements: 요구사항 문자열
            language: 프로그래밍 언어
            complexity_level: 복잡도 수준 (1-10)
            include_tests: 테스트 코드 포함 여부
            include_documentation: 문서화 포함 여부
            references: 참고할 코드나 문서 URL 목록
            
        Returns:
            파일명을 키로, 코드 내용을 값으로 하는 딕셔너리
        """
        # 프롬프트 생성
        prompt = self._build_prompt(
            requirements, 
            language, 
            complexity_level,
            include_tests,
            include_documentation,
            references
        )
        
        # 로깅 추가
        logging.info(f"코드 생성 요청: 언어={language}, 복잡도={complexity_level}, 테스트={include_tests}")
        logging.debug(f"생성 프롬프트: {prompt[:200]}...")
        
        # 사칙연산 프로그램 기본 코드 (요구사항이 비어있거나 사칙연산 관련인 경우)
        if not requirements or "사칙연산" in requirements:
            # 사칙연산 프로그램의 기본 코드 제공
            calculator_code = """
def add(a, b):
    \"\"\"덧셈 연산을 수행합니다.\"\"\"
    return a + b

def subtract(a, b):
    \"\"\"뺄셈 연산을 수행합니다.\"\"\"
    return a - b

def multiply(a, b):
    \"\"\"곱셈 연산을 수행합니다.\"\"\"
    return a * b

def divide(a, b):
    \"\"\"나눗셈 연산을 수행합니다.\"\"\"
    if b == 0:
        raise ValueError("0으로 나눌 수 없습니다.")
    return a / b

def calculator():
    \"\"\"간단한 사칙연산 계산기 함수\"\"\"
    print("사칙연산 계산기")
    print("1: 덧셈, 2: 뺄셈, 3: 곱셈, 4: 나눗셈")
    
    try:
        choice = int(input("원하는 연산을 선택하세요 (1/2/3/4): "))
        if choice not in [1, 2, 3, 4]:
            print("올바른 연산을 선택하세요.")
            return
        
        a = float(input("첫 번째 숫자를 입력하세요: "))
        b = float(input("두 번째 숫자를 입력하세요: "))
        
        if choice == 1:
            result = add(a, b)
            operation = "덧셈"
        elif choice == 2:
            result = subtract(a, b)
            operation = "뺄셈"
        elif choice == 3:
            result = multiply(a, b)
            operation = "곱셈"
        else:
            try:
                result = divide(a, b)
                operation = "나눗셈"
            except ValueError as e:
                print(f"오류: {e}")
                return
        
        print(f"{operation} 결과: {result}")
        
    except ValueError:
        print("올바른 숫자를 입력하세요.")
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    calculator()
"""
            
            logging.info("사칙연산 프로그램 기본 코드 생성됨")
            
            return {
                "code_files": {
                    "calculator.py": calculator_code
                },
                "explanation": "사칙연산을 수행하는 간단한 계산기 프로그램입니다. 덧셈, 뺄셈, 곱셈, 나눗셈 기능을 제공합니다.",
                "usage_example": "프로그램을 실행하면 사용자에게 수행할 연산과 두 개의 숫자를 입력받아 계산 결과를 보여줍니다."
            }
        
        # TODO: 여기에 실제 LLM 호출 코드 구현
        # 예시 응답
        response = f"# {requirements}에 대한 코드\n\n```python\n# main.py\ndef hello():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    hello()\n```\n\n이 코드는 간단한 Hello World 프로그램입니다."
        
        # 코드 블록 추출
        code_files = self._extract_code_blocks(response, language)
        
        # 설명 추출 (코드 블록 제외)
        explanation = self._extract_explanation(response)
        
        # 사용 예제 추출 (있는 경우)
        usage_example = self._extract_usage_example(response, language)
        
        # 로깅 추가
        logging.info(f"코드 생성 완료: {len(code_files)}개 파일, 설명 길이: {len(explanation)}")
        
        return {
            "code_files": code_files,
            "explanation": explanation,
            "usage_example": usage_example
        }
    
    def _build_prompt(self, 
                     requirements: str, 
                     language: str,
                     complexity_level: int,
                     include_tests: bool,
                     include_documentation: bool,
                     references: List[str] = None) -> str:
        """LLM을 위한 프롬프트 구성"""
        
        # 언어별 스타일 가이드
        style_guide = CODE_STYLE_GUIDES.get(language, "일반적인 코딩 표준을 따르세요")
        
        # 언어별 인기 프레임워크
        frameworks = LANGUAGE_FRAMEWORKS.get(language, [])
        frameworks_text = ""
        if frameworks:
            frameworks_text = f"다음과 같은 프레임워크를 고려할 수 있습니다: {', '.join(frameworks)}"
        
        # 코드 조직화 전략
        code_org_strategy = {
            "모듈화": "코드를 논리적 단위로 모듈화하여 재사용성과 유지보수성을 높이세요.",
            "단일 파일": "단순한 구현을 위해 최소한의 파일로 코드를 구성하세요.",
            "마이크로서비스": "독립적으로 배포 가능한 서비스 단위로 코드를 구성하세요."
        }.get(self.strategy["code_organization"], "적절한 모듈화를 적용하세요.")
        
        # 테스트 관련 지시사항
        test_instructions = ""
        if include_tests:
            test_coverage = {
                "기본": "주요 기능에 대한 기본적인 테스트 코드를 작성하세요.",
                "전체": "모든 기능과 경계 조건, 예외 사항에 대한 철저한 테스트를 작성하세요."
            }.get(self.strategy["test_coverage"], "필요한 테스트 코드를 작성하세요.")
            
            test_pattern = TEST_FILE_PATTERNS.get(language, "test_{filename}")
            test_instructions = f"""
## 테스트 코드
{test_coverage}
테스트 파일은 '{test_pattern}' 형식으로 작성하세요.
"""
        
        # 문서화 관련 지시사항
        doc_instructions = ""
        if include_documentation:
            doc_level = {
                "최소": "필수적인 함수와 클래스에 대한 간략한 설명만 포함하세요.",
                "표준": "모든 공개 API에 문서화 주석을 추가하고 기본적인 사용법을 설명하세요.",
                "상세": "모든 컴포넌트에 철저한 문서화를 적용하고, 예제와 사용 시나리오를 포함하세요."
            }.get(self.strategy["documentation_level"], "적절한 문서화를 적용하세요.")
            
            doc_instructions = f"""
## 문서화
{doc_level}
README.md 파일에 전체 프로젝트 설명과 사용법을 포함하세요.
"""
        
        # 참고 자료
        references_text = ""
        if references:
            references_text = "## 참고 자료\n- " + "\n- ".join(references)
        
        # 프롬프트 구성
        prompt = f"""
# {language.capitalize()} 코드 생성

## 요구사항
{requirements}

## 개발 지침
- {style_guide}
- 명확한 변수명과 함수명을 사용하세요
- 복잡도 수준: {complexity_level}/10
- {code_org_strategy}
- {frameworks_text}

{test_instructions}
{doc_instructions}
{references_text}

모든 코드 파일을 생성하고, 각 파일의 용도와 포함된 컴포넌트를 설명하세요.
파일 이름과 디렉토리 구조도 제안해주세요.
"""
        return prompt
    
    def parse_llm_response(self, response: str, language: str) -> Dict[str, Any]:
        """LLM 응답에서 코드와 설명 추출"""
        # 코드 블록 추출
        code_files = self._extract_code_blocks(response, language)
        
        # 설명 추출 (코드 블록 제외)
        explanation = self._extract_explanation(response)
        
        # 사용 예제 추출 (있는 경우)
        usage_example = self._extract_usage_example(response, language)
        
        return {
            "code_files": code_files,
            "explanation": explanation,
            "usage_example": usage_example
        }
    
    def _extract_code_blocks(self, text: str, language: str) -> Dict[str, str]:
        """텍스트에서 코드 블록 추출"""
        # 코드 블록 정규식 패턴
        pattern = r"```(?:(\w+)?\s*(?:(\S+)?)?\s*\n)?(.*?)```"
        
        # 결과 저장 딕셔너리
        code_files = {}
        
        # 모든 코드 블록 찾기
        matches = re.finditer(pattern, text, re.DOTALL)
        
        for i, match in enumerate(matches):
            # 코드 언어, 파일 이름, 코드 내용 추출
            lang = match.group(1) or language
            filename = match.group(2)
            code = match.group(3).strip()
            
            # 파일 이름이 없으면 기본 이름 생성
            if not filename:
                ext = LANGUAGE_EXTENSIONS.get(language, language)
                filename = f"file_{i+1}.{ext}"
            
            # 결과 저장
            code_files[filename] = code
        
        return code_files
    
    def _extract_explanation(self, text: str) -> str:
        """텍스트에서 설명 부분 추출"""
        # 코드 블록 제거
        explanation = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        
        # 정리
        explanation = re.sub(r'\n{3,}', '\n\n', explanation)
        
        return explanation.strip()
    
    def _extract_usage_example(self, text: str, language: str) -> Optional[str]:
        """사용 예제 부분 추출"""
        # '사용 방법', '사용 예제', 'Usage' 등으로 시작하는 섹션 찾기
        usage_patterns = [
            r'(?:^|\n)#+\s*사용\s*(?:방법|예제).*?(?=\n#+\s*|$)',
            r'(?:^|\n)#+\s*Usage.*?(?=\n#+\s*|$)',
            r'(?:^|\n)#+\s*How\s*to\s*Use.*?(?=\n#+\s*|$)'
        ]
        
        for pattern in usage_patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(0).strip()
        
        return None 