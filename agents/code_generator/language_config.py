"""
프로그래밍 언어별 설정과 지원 데이터
"""

# 언어별 파일 확장자
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
    "ruby": "rb",
    "swift": "swift",
    "kotlin": "kt"
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
    "ruby": "{filename}_test.rb",
    "swift": "{filename}Tests.swift",
    "kotlin": "{filename}Test.kt"
}

# 언어별 주요 프레임워크
LANGUAGE_FRAMEWORKS = {
    "python": ["Flask", "Django", "FastAPI", "PyTorch", "TensorFlow", "Pandas", "NumPy"],
    "javascript": ["React", "Vue", "Angular", "Express", "Next.js", "Node.js"],
    "typescript": ["React", "Angular", "Next.js", "NestJS", "Express"],
    "java": ["Spring Boot", "Hibernate", "Jakarta EE", "Android SDK"],
    "csharp": [".NET Core", "ASP.NET", "Entity Framework", "Xamarin"],
    "go": ["Gin", "Echo", "Fiber", "gRPC-Go"],
    "rust": ["Actix", "Rocket", "Tokio", "Yew"],
    "cpp": ["Qt", "Boost", "OpenCV", "TensorFlow C++"],
    "php": ["Laravel", "Symfony", "WordPress", "CodeIgniter"],
    "ruby": ["Ruby on Rails", "Sinatra", "Jekyll"],
    "swift": ["SwiftUI", "UIKit", "Combine", "Core Data"],
    "kotlin": ["Ktor", "Spring Boot", "Android SDK", "Compose"]
}

# 언어별 코드 스타일 가이드
CODE_STYLE_GUIDES = {
    "python": "PEP 8 스타일 가이드를 준수하세요",
    "javascript": "Airbnb JavaScript 스타일 가이드를 참고하세요",
    "typescript": "TypeScript 공식 스타일 가이드를 따르세요",
    "java": "Google Java 스타일 가이드를 준수하세요",
    "csharp": "Microsoft C# 코딩 컨벤션을 따르세요",
    "go": "Go 공식 스타일 가이드를 준수하세요",
    "rust": "Rust 공식 스타일 가이드를 따르세요",
    "cpp": "Google C++ 스타일 가이드를 준수하세요",
    "php": "PSR-12 코딩 표준을 따르세요",
    "ruby": "Ruby 스타일 가이드를 준수하세요",
    "swift": "Swift 공식 API 디자인 가이드라인을 따르세요",
    "kotlin": "Kotlin 공식 코딩 컨벤션을 준수하세요"
}

# 언어별 프로젝트 구조
PROJECT_STRUCTURES = {
    "python": {
        "simple": ["main.py", "README.md"],
        "standard": ["main.py", "utils.py", "config.py", "README.md"],
        "advanced": [
            "main.py",
            "src/__init__.py",
            "src/core/__init__.py",
            "src/utils/__init__.py",
            "tests/__init__.py",
            "config.py",
            "README.md"
        ]
    },
    "javascript": {
        "simple": ["index.js", "package.json", "README.md"],
        "standard": [
            "index.js", 
            "src/utils.js", 
            "package.json", 
            ".eslintrc.js", 
            "README.md"
        ],
        "advanced": [
            "index.js",
            "src/components/",
            "src/services/",
            "src/utils/",
            "tests/",
            "package.json",
            ".eslintrc.js",
            "webpack.config.js",
            "README.md"
        ]
    },
    # 다른 언어 구조도 필요에 따라 추가
}

# 언어별 문서화 템플릿
DOCUMENTATION_TEMPLATES = {
    "python": {
        "function": '''
        """
        함수 설명
        
        Args:
            param1 (type): 파라미터 설명
            
        Returns:
            type: 반환값 설명
            
        Raises:
            Exception: 예외 설명
        """
        ''',
        "class": '''
        """
        클래스 설명
        
        Attributes:
            attr1 (type): 속성 설명
        """
        '''
    },
    "javascript": {
        "function": '''
        /**
         * 함수 설명
         * 
         * @param {type} param1 - 파라미터 설명
         * @returns {type} 반환값 설명
         * @throws {Error} 예외 설명
         */
        ''',
        "class": '''
        /**
         * 클래스 설명
         * 
         * @property {type} attr1 - 속성 설명
         */
        '''
    },
    # 다른 언어 템플릿도 필요에 따라 추가
}

# 언어별 기본 프롬프트 템플릿
PROMPT_TEMPLATES = {
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
    "javascript": """
# JavaScript 코드 생성 요청
## 요구 사항
{requirements}

## 고려 사항
- 현대적인 JavaScript 문법(ES6+)을 사용해주세요
- 명확한 변수명과 함수명을 사용해주세요
- JSDoc을 사용한 문서화를 추가해주세요
- 모듈화 원칙을 적용해주세요
- 오류 처리를 적절히 포함해주세요
- 복잡도 수준: {complexity_level}/10

{test_requirements}
{doc_requirements}
{references_text}

모든 코드 파일을 생성하고, 각 파일의 용도와 내용을 설명해주세요.
""",
    # 다른 언어 템플릿도 필요에 따라 추가
} 