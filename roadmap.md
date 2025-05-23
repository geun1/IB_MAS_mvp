# 프로젝트 로드맵 및 체크리스트

## 1단계: 시스템 뼈대 준비 (Infra + 통신 기반)

| 항목                                         | 설명                                                                        | 체크 |
| -------------------------------------------- | --------------------------------------------------------------------------- | ---- |
| FastAPI 기반 프로젝트 구조 생성              | Orchestrator, Broker, Agent, Registry 등 디렉토리 구분                      | [x]  |
| Docker + Docker Compose 설정                 | Redis, RabbitMQ, 각 컴포넌트 컨테이너로 구성                                | [x]  |
| Redis, RabbitMQ 기본 통신 테스트             | Redis: key set/get, PubSub<br>RabbitMQ: 브로커-에이전트 간 메시지 전송 확인 | [x]  |
| LLM 호출 wrapper (LLMClient or litellm) 구현 | 다양한 provider 지원 구조                                                   | [x]  |

## 2단계: Agent Registry & 기본 Agent 구축

| 항목                                 | 설명                                                    | 체크 |
| ------------------------------------ | ------------------------------------------------------- | ---- |
| Registry 모듈 구현 (FastAPI + Redis) | agent 등록, 갱신, 조회 API (/register, /list)           | [x]  |
| Agent 구조 설계 (role, param schema) | 예: web_search, summarizer, writer 등 정의              | [x]  |
| 기본 Agent 구현 2~3개                | /run, /heartbeat endpoint 포함<br>입력 param validation | [x]  |
| 에이전트 등록 자동화                 | 실행 시 자동 등록 → TTL 설정                            | [x]  |
| Registry 조회 API 구현               | GET /agents/by-role?role=xxx                            | [x]  |

## 3단계: Broker 구현

| 항목                              | 설명                                     | 체크 |
| --------------------------------- | ---------------------------------------- | ---- |
| Broker 기본 구조 생성             | FastAPI + RabbitMQ consumer              | [x]  |
| Task 수신 → Agent 매핑 로직 구현  | registry 기반 role → agent 선택          | [x]  |
| Param 채우기 로직 구현 (LLM 호출) | 입력 부족 시 LLM 통해 param 완성 시도    | [x]  |
| 재질문 판단 로직                  | param 추론 실패 시 → 유저에게 물어보기   | [x]  |
| Agent 호출 & 응답 반환            | HTTP or queue 방식으로 실행 후 결과 수집 | [x]  |

## 4단계: Orchestrator (Planner) 구축

| 항목                                      | 설명                                          | 체크 |
| ----------------------------------------- | --------------------------------------------- | ---- |
| Orchestrator API (/query) 구현            | Client 요청 수신                              | [x]  |
| 유저 자연어 → task 분해 LLM 프롬프트 설계 | role list를 context로 제공                    | [x]  |
| 각 Task에 role 지정 로직                  | 예: write_report 요청 → web_search, writer 등 | [x]  |
| 생성된 task를 broker에 전달               | RabbitMQ or HTTP 방식                         | [x]  |
| 작업 완료 응답 취합 → Client 전달         | 병렬 처리 고려                                | [x]  |

## 5단계: ReACT Agent 구현

| 항목                                   | 설명                                                | 체크 |
| -------------------------------------- | --------------------------------------------------- | ---- |
| ReACT 기본 클래스 설계                 | 추론-행동-관찰-반복 패턴 구현, 상태 관리 인터페이스 | [x]  |
| 브로커 태스크 위임 시스템 확장         | ReACT 에이전트 제외 로직, 태스크 위임 API 추가      | [x]  |
| Fallback 매니저 구현                   | 실패 감지, 재시도 전략, 대체 계획 수립 기능         | [x]  |
| 태스크 상태 관리 매커니즘              | 진행 중/완료/실패 상태 추적, 결과 캐싱              | [x]  |
| 에이전트 별 Fallback 로직 커스터마이징 | 각 에이전트 특성에 맞는 복구 전략 정의              | [x]  |
| ReACT 도구 사용 메커니즘               | 브로커 기반 태스크 호출, 결과 처리                  | [x]  |
| 중간 상태 모니터링 API                 | ReACT 에이전트 진행 상황 확인 엔드포인트            | [x]  |

## 7단계: LLM 교체/호환성, 로깅/테스트

| 항목                                | 설명                                        | 체크 |
| ----------------------------------- | ------------------------------------------- | ---- |
| 모든 LLM 호출 → wrapper 구조로 통일 | LLMClient, litellm 등으로 centralize        | [x]  |
| 각 컴포넌트에 tracing ID 도입       | log 추적성 개선                             | [x]  |
| 기본 로깅 구성                      | loguru + task id 기준 trace                 | [x]  |
| ReACT 에이전트 테스트 시나리오      | 복잡한 다단계 요청, 오류 복구 테스트 케이스 | [x]  |
| Fallback 로직 테스트                | 다양한 실패 상황에서 복구 능력 검증         | [x]  |

## 8단계: ReACT UI 및 사용자 경험 개선

| 항목                                  | 설명                                    | 체크 |
| ------------------------------------- | --------------------------------------- | ---- |
| ReACT 진행 과정 시각화 컴포넌트       | 사고-행동-관찰 루프 시각화 UI           | [x]  |
| Fallback 발생 알림 및 개입 인터페이스 | 오류 발생 시 사용자 선택 옵션 제공      | [x]  |
| 중간 결과 미리보기                    | 진행 중인 ReACT 태스크의 부분 결과 표시 | [x]  |
| 디버깅 도구 및 로그 뷰어              | 개발자용 진단 인터페이스                | [x]  |
