from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import httpx
import os
import json
from typing import Dict, List, Optional, Any
import time
import asyncio
import psutil
from datetime import datetime
import logging
from enum import Enum
import uuid
import sys

# 현재 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from code_generator import CodeGenerator

# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="코드 생성 에이전트 API",
    description="요구사항에 따라 다양한 프로그래밍 언어로 코드를 생성하는 에이전트 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 로깅 설정
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("code_generator_agent")

# 상태 초기화
app.state.active_tasks = set()  # 활성 작업 추적을 위한 set

# 환경 변수 가져오기
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8000")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "20"))  # 기본값 20초

# 브로커 요청을 위한 새 모델 추가
class BrokerRequest(BaseModel):
    input: Dict[str, Any]
    task_id: Optional[str] = None
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

# 모델 정의
class ProgrammingLanguage(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CSHARP = "csharp"
    GO = "go"
    RUST = "rust"
    CPP = "cpp"
    PHP = "php"
    RUBY = "ruby"

class CodeGenerationRequest(BaseModel):
    requirements: str
    language: ProgrammingLanguage = ProgrammingLanguage.PYTHON
    include_tests: bool = False
    include_documentation: bool = True
    complexity_level: Optional[int] = None  # 1-10 범위의 코드 복잡성 (없으면 자동 결정)
    references: Optional[List[str]] = None  # 참고할 코드 샘플이나 문서 URL
    
class CodeGenerationResponse(BaseModel):
    code: Dict[str, str]  # 파일 이름을 키로, 코드 내용을 값으로
    explanation: str
    usage_example: Optional[str] = None

# 초기 등록을 위한 변수들
AGENT_ID = "code_generator_agent_1"
AGENT_ROLE = "code_generator"
AGENT_DESCRIPTION = "사용자 요구사항에 따라 구조화된 코드를 생성합니다. 다양한 프로그래밍 언어를 지원하며, 테스트 코드와 문서화 옵션이 있습니다."

# 등록 태스크
async def register_agent():
    """레지스트리에 에이전트 등록"""
    try:
        # 컨테이너 외부에서 접근 가능한 엔드포인트 구성
        container_name = os.getenv("CONTAINER_NAME", "code_generator_agent")
        port = int(os.getenv("PORT", "8000"))
        
        # 포트가 기본 8000이 아닌 경우를 처리
        if port != 8000:
            service_endpoint = f"http://{container_name}:{port}/generate_code"
        else:
            service_endpoint = f"http://{container_name}:8000/generate_code"
        
        # 에이전트 데이터 준비
        agent_data = {
            "id": AGENT_ID,  # agent_id 대신 id 사용
            "role": AGENT_ROLE,
            "description": AGENT_DESCRIPTION,
            "endpoint": service_endpoint,
            "type": "function",
            "params": [
                {
                    "name": "requirements",
                    "description": "코드 생성을 위한 요구사항 및 기능 설명",
                    "required": True,
                    "type": "string"
                },
                {
                    "name": "language",
                    "description": "사용할 프로그래밍 언어 (python, javascript, typescript, java, csharp 등)",
                    "required": False,
                    "type": "string",
                    "default": "python" 
                },
                {
                    "name": "include_tests",
                    "description": "테스트 코드를 포함할지 여부",
                    "required": False,
                    "type": "boolean",
                    "default": False
                },
                {
                    "name": "include_documentation",
                    "description": "코드 문서화를 포함할지 여부",
                    "required": False,
                    "type": "boolean",
                    "default": True
                },
                {
                    "name": "complexity_level",
                    "description": "코드 복잡성 수준 (1-10)",
                    "required": False,
                    "type": "number",
                    "default": 5
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{REGISTRY_URL}/register",
                json=agent_data
            )
            logger.info(f"에이전트 등록 응답: {response.status_code}, {response.text}")
            return response.status_code == 201
            
    except Exception as e:
        logger.error(f"에이전트 등록 실패: {str(e)}")
        return False

async def _get_agent_parameters():
    """에이전트의 API 엔드포인트 및 파라미터 정보 생성"""
    return [
        {
            "name": "requirements",
            "type": "string",
            "description": "코드 생성을 위한 요구사항 및 기능 설명",
            "required": True
        },
        {
            "name": "language",
            "type": "string",
            "description": "사용할 프로그래밍 언어 (python, javascript, typescript, java, csharp 등)",
            "required": False,
            "default": "python" 
        },
        {
            "name": "include_tests",
            "type": "boolean",
            "description": "테스트 코드를 포함할지 여부",
            "required": False,
            "default": False
        },
        {
            "name": "include_documentation",
            "type": "boolean",
            "description": "코드 문서화를 포함할지 여부",
            "required": False,
            "default": True
        },
        {
            "name": "complexity_level",
            "type": "number",  # 'integer'에서 'number'로 변경
            "description": "코드 복잡성 수준 (1-10)",
            "required": False,
            "default": 5
        }
    ]

# 하트비트 보내기
async def send_heartbeat():
    """Registry에 하트비트 전송"""
    while True:
        try:
            # 현재 메모리, CPU 사용량 측정
            memory_usage = psutil.virtual_memory().percent
            cpu_usage = psutil.cpu_percent()
            
            # 활성 태스크 수 계산
            active_tasks_count = len(app.state.active_tasks)
            
            # Heartbeat 데이터 형식
            heartbeat_data = {
                "status": "active",
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "memory_usage": memory_usage,
                    "cpu_usage": cpu_usage,
                    "active_tasks": active_tasks_count
                },
                "version": "1.0.0"
            }
            
            # Registry에 heartbeat 전송
            url = f"{REGISTRY_URL}/heartbeat/{AGENT_ROLE}/{AGENT_ID}"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=heartbeat_data, timeout=5)
                if response.status_code == 200:
                    logger.debug("Heartbeat 전송 성공")
                else:
                    logger.warning(f"Heartbeat 전송 실패: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Heartbeat 전송 중 오류: {str(e)}")
        
        await asyncio.sleep(HEARTBEAT_INTERVAL)

# 시작 시 등록
@app.on_event("startup")
async def startup_event():
    # 에이전트 등록
    await register_agent()
    
    # 하트비트 태스크 시작
    asyncio.create_task(send_heartbeat())

# 루트 경로에도 동일한 핸들러 등록 (호환성 유지)
@app.post("/")
async def run_task_root(task: dict):
    """루트 경로 태스크 실행 (호환성용)"""
    return await run_task(task)

# 언어별 파일 확장자 매핑
LANGUAGE_EXTENSIONS = {
    "python": "py",
    "javascript": "js",
    "typescript": "ts",
    "java": "java",
    "csharp": "cs",
    "go": "go",
    "rust": "rs",
    "cpp": "cpp",
    "php": "php",
    "ruby": "rb"
}

# 언어별 테스트 파일 명명 규칙
TEST_FILE_PATTERNS = {
    "python": "test_{filename}.py",
    "javascript": "{filename}.test.js",
    "typescript": "{filename}.test.ts",
    "java": "{filename}Test.java",
    "csharp": "{filename}Tests.cs",
    "go": "{filename}_test.go",
    "rust": "{filename}_test.rs",
    "cpp": "{filename}_test.cpp",
    "php": "{filename}Test.php",
    "ruby": "{filename}_test.rb"
}

# 언어별 프로젝트 구조 가이드 (간략화된 버전)
PROJECT_STRUCTURES = {
    "python": {
        "main": "main.py",
        "lib": "{module_name}.py",
        "test": "tests/test_{module_name}.py",
        "docs": "README.md"
    },
    "javascript": {
        "main": "index.js",
        "lib": "src/{module_name}.js",
        "test": "tests/{module_name}.test.js",
        "docs": "README.md"
    },
    # 다른 언어들도 유사하게 추가...
}

# 언어별 코드 생성을 위한 프롬프트 템플릿
CODE_GENERATION_PROMPTS = {
    "python": """
# Python 코드 생성 요청
## 요구 사항
{requirements}

## 고려 사항
- PEP 8 스타일 가이드를 따라주세요
- 명확한 변수명과 함수명을 사용해주세요
- 적절한 주석과 문서화 문자열을 추가해주세요
- 모듈화와 객체지향 원칙을 적용해주세요
- 예외 처리를 적절히 포함해주세요
- 복잡도 수준: {complexity_level}/10

{test_requirements}
{doc_requirements}
{references_text}

모든 코드 파일을 생성하고, 각 파일의 용도와 내용을 설명해주세요.
""",
    # 다른 언어들도 유사하게 추가...
}

@app.post("/generate_code")
async def generate_code(request: CodeGenerationRequest):
    """코드 생성 API 엔드포인트"""
    task_id = str(uuid.uuid4())
    logger.info(f"코드 생성 요청 수신: {task_id}")
    
    # 작업 추적을 위해 활성 태스크에 추가
    app.state.active_tasks.add(task_id)
    
    try:
        # 요청 파라미터 추출
        requirements = request.requirements
        language = request.language
        include_tests = request.include_tests
        include_documentation = request.include_documentation
        complexity_level = request.complexity_level or 5
        references = request.references or []
        
        # 코드 생성기 인스턴스 생성
        code_gen = CodeGenerator()
        
        # 코드 생성 프롬프트 구성
        prompt = code_gen._build_prompt(
            requirements=requirements,
            language=language,
            complexity_level=complexity_level,
            include_tests=include_tests,
            include_documentation=include_documentation,
            references=references
        )
        
        # LLM 호출 (Claude 또는 OpenAI)
        # 실제 프로덕션에서는 litellm 등을 사용하여 LLM API 호출
        # 여기서는 간단한 예시 코드 생성으로 대체
        
        # 언어별 예제 코드 생성
        generated_code = generate_simple_example(language, requirements)
        
        # 결과 구성
        result = {
            "code_files": {
                f"main.{LANGUAGE_EXTENSIONS.get(language, 'py')}": generated_code
            },
            "explanation": f"요구사항 '{requirements}'에 따라 {language} 코드를 생성하였습니다.",
            "task_id": task_id,
            "language": language,
            "requirements": requirements
        }
        
        # 테스트 포함 시 테스트 코드 추가
        if include_tests:
            test_file_name = TEST_FILE_PATTERNS.get(language, "test_main.py").format(filename="main")
            result["code_files"][test_file_name] = _generate_test_code(language, requirements)
        
        logger.info(f"코드 생성 완료: {task_id}")
        return result
    
    except Exception as e:
        logger.error(f"코드 생성 중 오류: {str(e)}")
        return {"error": str(e), "task_id": task_id}
    
    finally:
        # 작업 완료 후 활성 태스크에서 제거
        if task_id in app.state.active_tasks:
            app.state.active_tasks.remove(task_id)

@app.post("/run")
async def run(request: Request):
    """표준 에이전트 실행 엔드포인트"""
    logger.info("브로커에서 /run으로 요청이 들어왔습니다")
    return await generate_code_run(request)

@app.post("/generate_code/run")
async def generate_code_run(request: Request):
    """브로커가 자동으로 구성한 경로에 대응하는 엔드포인트"""
    logger.info("브로커에서 /generate_code/run으로 요청이 들어왔습니다")
    
    try:
        # 요청 본문을 JSON으로 파싱
        data = await request.json()
        logger.info(f"받은 요청 데이터: {data}")
        
        # 요청 데이터에서 필요한 정보 추출
        input_data = data.get("input", {})
        task_id = data.get("task_id", str(uuid.uuid4()))
        
        # 기존 generate_code 엔드포인트 호출을 위한 요청 변환
        code_request = CodeGenerationRequest(
            requirements=input_data.get("requirements", ""),
            language=input_data.get("language", ProgrammingLanguage.PYTHON),
            include_tests=input_data.get("include_tests", False),
            include_documentation=input_data.get("include_documentation", True),
            complexity_level=input_data.get("complexity_level", 5),
            references=input_data.get("references", [])
        )
        
        # 기존 generate_code 엔드포인트 호출
        result = await generate_code(code_request)
        return result
    except Exception as e:
        logger.error(f"브로커 요청 처리 중 오류: {str(e)}")
        return {"error": str(e), "task_id": task_id if 'task_id' in locals() else str(uuid.uuid4())}

def parse_code_blocks(text, language):
    """텍스트에서 코드 블록 추출"""
    import re
    
    # 코드 블록 패턴
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
    
    # 코드 블록이 없거나 추출 실패한 경우 처리
    if not code_files:
        # 대안 방법으로 다시 시도
        code_sections = re.split(r'(?i)^#{1,3}\s*(?:파일|file):\s*(\S+)', text)[1:]
        
        if code_sections:
            for i in range(0, len(code_sections), 2):
                if i+1 < len(code_sections):
                    filename = code_sections[i].strip()
                    code = code_sections[i+1].strip()
                    
                    # 코드 부분에서 마크다운 코드 블록 형식 제거
                    code = re.sub(r'```.*?\n', '', code)
                    code = re.sub(r'```', '', code)
                    
                    code_files[filename] = code.strip()
    
    return code_files

def extract_explanation(text):
    """텍스트에서 설명 부분 추출 (코드 블록 제외)"""
    import re
    
    # 코드 블록 제거
    explanation = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    
    # 정리
    explanation = re.sub(r'\n{3,}', '\n\n', explanation)
    
    return explanation.strip()

def format_result_as_markdown(code_files, explanation, language):
    """결과를 마크다운 형식으로 포맷팅"""
    result = "# 코드 생성 결과\n\n"
    
    # 설명 부분 추가
    result += f"{explanation}\n\n"
    
    # 생성된 파일 목록
    result += "## 생성된 파일 목록\n\n"
    for filename in code_files:
        result += f"- `{filename}`\n"
    
    result += "\n## 코드 파일\n\n"
    
    # 각 코드 파일 추가
    for filename, code in code_files.items():
        # 파일 확장자에서 언어 유추
        file_ext = filename.split('.')[-1]
        lang = LANGUAGE_EXTENSIONS.get(language, file_ext)
        
        result += f"### {filename}\n\n"
        result += f"```{lang}\n{code}\n```\n\n"
    
    # 사용 예제
    result += "## 사용 방법\n\n"
    result += "위 코드를 다음과 같이 사용할 수 있습니다:\n\n"
    
    # 언어별 예제 실행 방법
    if language == "python":
        result += "```bash\n# Python 코드 실행\npython main.py\n```\n\n"
    elif language in ["javascript", "typescript"]:
        result += "```bash\n# JavaScript/TypeScript 코드 실행\nnode index.js\n```\n\n"
    # 다른 언어 예제...
    
    return result

def generate_simple_example(language, requirements):
    """간단한 예제 코드 생성"""
    if language == "python":
        return f"""# {requirements}에 대한 간단한 예제
def main():
    print("요구사항: {requirements}")
    # 여기에 실제 구현 필요
    return "구현 필요"

if __name__ == "__main__":
    result = main()
    print(result)
"""
    elif language == "javascript":
        return f"""// {requirements}에 대한 간단한 예제
function main() {{
  console.log("요구사항: {requirements}");
  // 여기에 실제 구현 필요
  return "구현 필요";
}}

main();
"""
    # 다른 언어에 대한 간단한 예제도 추가...
    else:
        return f"// {requirements}에 대한 {language} 코드 구현이 필요합니다."

def _generate_test_code(language, requirements):
    """테스트 코드 생성 함수"""
    if language == "python":
        return f"""# {requirements}에 대한 테스트 코드
import unittest
from main import main

class TestMain(unittest.TestCase):
    def test_main_function(self):
        # 테스트 구현 필요
        result = main()
        self.assertIsNotNone(result)

if __name__ == "__main__":
    unittest.main()
"""
    elif language == "javascript":
        return f"""// {requirements}에 대한 테스트 코드
const assert = require('assert');
const main = require('./main');

describe('메인 함수 테스트', function() {{
  it('결과가 존재해야 함', function() {{
    // 테스트 구현 필요
    const result = main();
    assert(result !== null);
  }});
}});
"""
    # 다른 언어에 대한 테스트 코드 예제도 추가...
    else:
        return f"// {requirements}에 대한 {language} 테스트 코드 구현이 필요합니다."

# 서버 상태 확인용 API
@app.get("/")
async def root():
    return {"status": "online", "service": "Code Generator Agent", "id": AGENT_ID, "role": AGENT_ROLE}

# 서버 상태 확인용 API
@app.get("/health")
async def health():
    return {"status": "healthy"}

# 종료 이벤트 핸들러 추가
@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 처리"""
    try:
        # 일반 unregister 엔드포인트 시도
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{REGISTRY_URL}/unregister",
                    params={"role": AGENT_ROLE, "agent_id": AGENT_ID}
                )
                logger.info(f"에이전트 등록 해제 응답: {response.status_code}")
                
                # 실패 시 백업 메서드 사용
                if response.status_code != 200:
                    backup_response = await client.post(
                        f"{REGISTRY_URL}/unregister_direct",
                        params={"role": AGENT_ROLE, "agent_id": AGENT_ID}
                    )
                    logger.info(f"백업 등록 해제 응답: {backup_response.status_code}")
            except Exception as req_error:
                logger.error(f"등록 해제 요청 중 오류: {str(req_error)}")
                
    except Exception as e:
        logger.error(f"에이전트 등록 해제 중 오류: {str(e)}") 