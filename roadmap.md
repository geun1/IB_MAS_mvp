# 프로젝트 로드맵 및 체크리스트

## 1단계: 시스템 뼈대 준비 (Infra + 통신 기반)

| 항목                                         | 설명                                                                        | 체크 |
| -------------------------------------------- | --------------------------------------------------------------------------- | ---- |
| FastAPI 기반 프로젝트 구조 생성              | Orchestrator, Broker, Agent, Registry 등 디렉토리 구분                      | [x]  |
| Docker + Docker Compose 설정                 | Redis, RabbitMQ, 각 컴포넌트 컨테이너로 구성                                | [x]  |
| Redis, RabbitMQ 기본 통신 테스트             | Redis: key set/get, PubSub<br>RabbitMQ: 브로커-에이전트 간 메시지 전송 확인 | []   |
| LLM 호출 wrapper (LLMClient or litellm) 구현 | 다양한 provider 지원 구조                                                   | []   |

## 2단계: Agent Registry & 기본 Agent 구축

| 항목                                 | 설명                                                    | 체크 |
| ------------------------------------ | ------------------------------------------------------- | ---- |
| Registry 모듈 구현 (FastAPI + Redis) | agent 등록, 갱신, 조회 API (/register, /list)           | []   |
| Agent 구조 설계 (role, param schema) | 예: web_search, summarizer, writer 등 정의              | []   |
| 기본 Agent 구현 2~3개                | /run, /heartbeat endpoint 포함<br>입력 param validation | []   |
| 에이전트 등록 자동화                 | 실행 시 자동 등록 → TTL 설정                            | []   |
| Registry 조회 API 구현               | GET /agents/by-role?role=xxx                            | []   |

## 3단계: Broker 구현

| 항목                              | 설명                                     | 체크 |
| --------------------------------- | ---------------------------------------- | ---- |
| Broker 기본 구조 생성             | FastAPI + RabbitMQ consumer              | []   |
| Task 수신 → Agent 매핑 로직 구현  | registry 기반 role → agent 선택          | []   |
| Param 채우기 로직 구현 (LLM 호출) | 입력 부족 시 LLM 통해 param 완성 시도    | []   |
| 재질문 판단 로직                  | param 추론 실패 시 → 유저에게 물어보기   | []   |
| Agent 호출 & 응답 반환            | HTTP or queue 방식으로 실행 후 결과 수집 | []   |

## 4단계: Orchestrator (Planner) 구축

| 항목                                      | 설명                                          | 체크 |
| ----------------------------------------- | --------------------------------------------- | ---- |
| Orchestrator API (/query) 구현            | Client 요청 수신                              | []   |
| 유저 자연어 → task 분해 LLM 프롬프트 설계 | role list를 context로 제공                    | []   |
| 각 Task에 role 지정 로직                  | 예: write_report 요청 → web_search, writer 등 | []   |
| 생성된 task를 broker에 전달               | RabbitMQ or HTTP 방식                         | []   |
| 작업 완료 응답 취합 → Client 전달         | 병렬 처리 고려                                | []   |

## 5단계: Client Loop + 재질문/오류 처리 흐름

| 항목                                  | 설명                                                                     | 체크 |
| ------------------------------------- | ------------------------------------------------------------------------ | ---- |
| 파라미터 부족 시 → 유저에게 질문 생성 | LLM 기반 질문 생성                                                       | []   |
| Client → 유저 입력 → 재시도 흐름 구현 | WebSocket or polling 기반                                                | []   |
| role 매칭 실패 시 fallback 처리       | 예: ppt_designer → "지원하지 않는 기능입니다" or "summarizer" 대체 사용" | []   |
| 유저 재시도 지원                      | 재질문 이후 파라미터 보완 요청 처리                                      | []   |

## 6단계: LLM 교체/호환성, 로깅/테스트

| 항목                                | 설명                                 | 체크 |
| ----------------------------------- | ------------------------------------ | ---- |
| 모든 LLM 호출 → wrapper 구조로 통일 | LLMClient, litellm 등으로 centralize | []   |
| 각 컴포넌트에 tracing ID 도입       | log 추적성 개선                      | []   |
| 기본 로깅 구성                      | loguru + task id 기준 trace          | []   |
| 샘플 시나리오 테스트                | "마케팅 최근 동향 보고서 써줘" 등    | []   |

## 디렉토리 구조 예시
