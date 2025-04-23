"""
생성된 코드 테스트를 위한 모듈
"""
import os
import re
import uuid
import subprocess
import tempfile
import logging
from typing import Dict, List, Optional, Any, Tuple
from language_config import LANGUAGE_EXTENSIONS

logger = logging.getLogger(__name__)

class TestRunner:
    """생성된 코드를 테스트하는 클래스"""
    
    def __init__(self):
        """테스트 러너 초기화"""
        self.supported_languages = {
            "python": {
                "run_cmd": "python {file}",
                "test_cmd": "pytest {file} -v",
                "install_cmd": "pip install -r requirements.txt"
            },
            "javascript": {
                "run_cmd": "node {file}",
                "test_cmd": "jest {file}",
                "install_cmd": "npm install"
            },
            "typescript": {
                "run_cmd": "ts-node {file}",
                "test_cmd": "jest {file}",
                "install_cmd": "npm install"
            },
            "java": {
                "run_cmd": "java -cp . {main_class}",
                "test_cmd": "javac {file} && java -cp . org.junit.runner.JUnitCore {test_class}",
                "install_cmd": "mvn install"
            },
            "go": {
                "run_cmd": "go run {file}",
                "test_cmd": "go test",
                "install_cmd": "go mod tidy"
            },
            # 다른 언어도 필요에 따라 추가
        }
    
    def test_code(self, code_files: Dict[str, str], language: str) -> Dict[str, Any]:
        """생성된 코드 테스트"""
        if language not in self.supported_languages:
            return {
                "success": False,
                "message": f"지원하지 않는 언어: {language}",
                "details": {}
            }
            
        # 임시 디렉토리 생성
        temp_dir = self._create_temp_project(code_files)
        
        try:
            # 의존성 설치
            install_result = self._install_dependencies(temp_dir, language)
            
            # 실행 테스트
            run_result = self._run_code(temp_dir, code_files, language)
            
            # 단위 테스트 실행 (해당하는 경우)
            test_result = self._run_tests(temp_dir, code_files, language)
            
            # 코드 정적 분석 (해당하는 경우)
            lint_result = self._lint_code(temp_dir, code_files, language)
            
            return {
                "success": run_result.get("success", False),
                "message": "코드 테스트 완료",
                "details": {
                    "install": install_result,
                    "run": run_result,
                    "test": test_result,
                    "lint": lint_result
                }
            }
                
        except Exception as e:
            logger.exception("코드 테스트 중 오류 발생")
            return {
                "success": False,
                "message": f"테스트 중 오류 발생: {str(e)}",
                "details": {}
            }
        finally:
            # 임시 디렉토리 정리
            self._cleanup_temp_project(temp_dir)
    
    def _create_temp_project(self, code_files: Dict[str, str]) -> str:
        """코드 파일로 임시 프로젝트 디렉토리 생성"""
        # 고유한 임시 디렉토리 생성
        temp_dir = tempfile.mkdtemp(prefix="code_test_")
        
        # 파일 생성
        for filename, content in code_files.items():
            # 디렉토리 구조 처리
            if '/' in filename:
                dir_path = os.path.join(temp_dir, os.path.dirname(filename))
                os.makedirs(dir_path, exist_ok=True)
                
            # 파일 작성
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return temp_dir
        
    def _install_dependencies(self, project_dir: str, language: str) -> Dict[str, Any]:
        """프로젝트 의존성 설치"""
        commands = {
            "python": ["pip", "install", "-r", "requirements.txt"],
            "javascript": ["npm", "install"],
            "typescript": ["npm", "install"],
            "java": ["mvn", "install"],
            "go": ["go", "mod", "tidy"],
        }
        
        # 언어별 의존성 설치 명령어
        cmd = commands.get(language)
        if not cmd:
            return {"success": True, "message": "의존성 설치 명령어가 정의되지 않음"}
            
        # requirements.txt 또는 package.json 같은 파일이 없으면 스킵
        if language == "python" and not os.path.exists(os.path.join(project_dir, "requirements.txt")):
            return {"success": True, "message": "requirements.txt 파일이 없음"}
        
        if language in ["javascript", "typescript"] and not os.path.exists(os.path.join(project_dir, "package.json")):
            return {"success": True, "message": "package.json 파일이 없음"}
            
        try:
            # 의존성 설치 실행
            result = subprocess.run(
                cmd, 
                cwd=project_dir, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "message": "의존성 설치 성공",
                    "output": result.stdout
                }
            else:
                return {
                    "success": False,
                    "message": "의존성 설치 실패",
                    "error": result.stderr
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"의존성 설치 중 오류: {str(e)}",
                "error": str(e)
            }
            
    def _run_code(self, project_dir: str, code_files: Dict[str, str], language: str) -> Dict[str, Any]:
        """코드 실행"""
        # 메인 파일 찾기
        main_file = self._find_main_file(code_files, language)
        if not main_file:
            return {
                "success": False, 
                "message": "실행할 메인 파일을 찾을 수 없음"
            }
        
        # 언어별 실행 명령어
        run_cmd_template = self.supported_languages.get(language, {}).get("run_cmd")
        if not run_cmd_template:
            return {
                "success": False, 
                "message": f"지원하지 않는 언어: {language}"
            }
            
        # 명령어 형식 지정
        run_cmd = run_cmd_template.format(file=main_file)
        run_cmd = run_cmd.split()
        
        try:
            # 코드 실행
            result = subprocess.run(
                run_cmd, 
                cwd=project_dir, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                timeout=10  # 10초 제한
            )
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "message": "코드 실행 성공",
                    "output": result.stdout
                }
            else:
                return {
                    "success": False,
                    "message": "코드 실행 실패",
                    "error": result.stderr
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "코드 실행 시간 초과 (10초)",
                "error": "실행 시간이 너무 깁니다"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"코드 실행 중 오류: {str(e)}",
                "error": str(e)
            }
    
    def _run_tests(self, project_dir: str, code_files: Dict[str, str], language: str) -> Dict[str, Any]:
        """테스트 실행"""
        # 테스트 파일 찾기
        test_files = self._find_test_files(code_files, language)
        if not test_files:
            return {
                "success": True, 
                "message": "테스트 파일이 없음"
            }
        
        # 언어별 테스트 명령어
        test_cmd_template = self.supported_languages.get(language, {}).get("test_cmd")
        if not test_cmd_template:
            return {
                "success": False, 
                "message": f"지원하지 않는 언어: {language}"
            }
            
        results = []
        for test_file in test_files:
            # 명령어 형식 지정
            test_cmd = test_cmd_template.format(file=test_file)
            test_cmd = test_cmd.split()
            
            try:
                # 테스트 실행
                result = subprocess.run(
                    test_cmd, 
                    cwd=project_dir, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30  # 30초 제한
                )
                
                results.append({
                    "file": test_file,
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr if result.returncode != 0 else ""
                })
                    
            except Exception as e:
                results.append({
                    "file": test_file,
                    "success": False,
                    "error": str(e)
                })
        
        # 모든 테스트가 성공했는지 확인
        all_success = all(r["success"] for r in results)
        
        return {
            "success": all_success,
            "message": "모든 테스트 통과" if all_success else "일부 테스트 실패",
            "details": results
        }
    
    def _lint_code(self, project_dir: str, code_files: Dict[str, str], language: str) -> Dict[str, Any]:
        """코드 정적 분석"""
        lint_commands = {
            "python": ["pylint", "--disable=C0111,C0103", "{file}"],
            "javascript": ["eslint", "{file}"],
            "typescript": ["eslint", "{file}"],
            "java": ["checkstyle", "-c", "/google_checks.xml", "{file}"],
            "go": ["golint", "{file}"],
        }
        
        # 언어별 린트 명령어
        lint_cmd_template = lint_commands.get(language)
        if not lint_cmd_template:
            return {
                "success": True, 
                "message": f"{language}용 린트 도구가 정의되지 않음"
            }
        
        results = []
        for filename in code_files:
            # 디렉토리는 건너뛰기
            if not os.path.splitext(filename)[1]:
                continue
                
            # 명령어 형식 지정
            lint_cmd = [cmd.format(file=filename) for cmd in lint_cmd_template]
            
            try:
                # 린트 실행
                result = subprocess.run(
                    lint_cmd, 
                    cwd=project_dir, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=10
                )
                
                results.append({
                    "file": filename,
                    "success": result.returncode == 0,
                    "issues": result.stdout if result.returncode != 0 else ""
                })
                    
            except Exception as e:
                results.append({
                    "file": filename,
                    "success": False,
                    "error": str(e)
                })
        
        # 모든 파일이 린트를 통과했는지 확인
        all_success = all(r["success"] for r in results)
        
        return {
            "success": all_success,
            "message": "모든 파일이 린트 검사 통과" if all_success else "일부 파일이 린트 검사 실패",
            "details": results
        }
    
    def _find_main_file(self, code_files: Dict[str, str], language: str) -> Optional[str]:
        """메인 파일 찾기"""
        # 언어별 메인 파일 후보
        main_candidates = {
            "python": ["main.py", "app.py", "__main__.py"],
            "javascript": ["index.js", "main.js", "app.js"],
            "typescript": ["index.ts", "main.ts", "app.ts"],
            "java": ["Main.java", "App.java"],
            "go": ["main.go"],
        }
        
        # 후보 파일 확인
        candidates = main_candidates.get(language, [])
        for candidate in candidates:
            if candidate in code_files:
                return candidate
                
        # 확장자로 찾기
        ext = "." + LANGUAGE_EXTENSIONS.get(language, language)
        for filename in code_files:
            if filename.endswith(ext):
                return filename
                
        return None
    
    def _find_test_files(self, code_files: Dict[str, str], language: str) -> List[str]:
        """테스트 파일 찾기"""
        # 언어별 테스트 파일 패턴
        test_patterns = {
            "python": [r"test_.*\.py", r".*_test\.py"],
            "javascript": [r".*\.test\.js", r".*_test\.js", r"test_.*\.js"],
            "typescript": [r".*\.test\.ts", r".*_test\.ts", r"test_.*\.ts"],
            "java": [r".*Test\.java"],
            "go": [r".*_test\.go"],
        }
        
        test_files = []
        patterns = test_patterns.get(language, [])
        
        for filename in code_files:
            for pattern in patterns:
                if re.match(pattern, filename):
                    test_files.append(filename)
                    break
                    
        return test_files
    
    def _cleanup_temp_project(self, project_dir: str) -> None:
        """임시 프로젝트 디렉토리 정리"""
        import shutil
        try:
            shutil.rmtree(project_dir)
        except Exception as e:
            logger.error(f"임시 디렉토리 정리 중 오류: {str(e)}") 