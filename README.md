# 멀티에이전트 서비스 시스템

## 소개

이 프로젝트는 다양한 기능을 수행하는 AI 에이전트들로 구성된 분산 시스템입니다. 사용자의 자연어 요청을 받아 적절한 에이전트들로 작업을 분배하고 결과를 취합하여 제공합니다.

## 주요 컴포넌트

-   **Registry**: 에이전트 등록 및 관리
-   **Orchestrator**: 사용자 요청 분석 및 작업 조율
-   **Broker**: 작업 라우팅 및 에이전트 선택
-   **Agents**: 다양한 기능을 수행하는 에이전트들
    -   Web Search Agent: 웹에서 정보 검색
    -   Writer Agent: 문서 작성
    -   (추가 예정)

## 시작하기

### 사전 요구사항

-   Docker 및 Docker Compose
-   Python 3.10 이상 (로컬 개발 시)

### 설치 및 실행

1. 환경 설정

bash
cp .env.example .env
.env 파일 수정 (API 키 등 설정)

2. Docker Compose로 서비스 실행
   bash
   docker-compose up

### API 접근

-   Registry: http://localhost:8000
-   Orchestrator: http://localhost:8001
-   Broker: http://localhost:8002
-   RabbitMQ 관리 UI: http://localhost:15672

### API 문서 (Swagger UI)

각 서비스는 Swagger UI를 통한 API 문서화 및 테스트 기능을 제공합니다:

-   **Registry API 문서**: http://localhost:8000/docs
-   **Orchestrator API 문서**: http://localhost:8001/docs
-   **Broker API 문서**: http://localhost:8002/docs
-   **Web Search 에이전트 API 문서**: http://localhost:[PORT]/docs
-   **Writer 에이전트 API 문서**: http://localhost:[PORT]/docs

Swagger UI에서는 다음과 같은 작업이 가능합니다:

-   각 API 엔드포인트의 상세 설명 및 파라미터 확인
-   API 직접 테스트 (Try it out 버튼)
-   요청 및 응답 예제 확인
-   API 모델 스키마 확인

또한 ReDoc 문서도 제공됩니다: http://localhost:[PORT]/redoc

## 로드맵

프로젝트의 개발 로드맵은 [roadmap.md](roadmap.md) 파일을 참조하세요.

## 아키텍처

시스템 아키텍처에 대한 자세한 내용은 [architecture.md](architecture.md) 파일을 참조하세요.
