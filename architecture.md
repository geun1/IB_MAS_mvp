# 멀티에이전트 서비스 아키텍처 정리

---

## 목표

> 동적 에이전트 추가, 삭제
> 다양한 모델 호환성
> 응답 결과의 명확성
> 유지보수 용이성

> 응답의 정확성을 위한 유저 인터렉션 UX
> 에이전트들간의 의사소통

---

## 주요 아키텍처 컴포넌트

### 1. **Client (유저 인터페이스)**

-   자연어 요청 전달
-   파라미터 보완 요청 응답
-   최종 결과 수신

### 2. **Orchestrator (AI 플래너)**

-   유저 요청을 태스크 단위로 분해
-   각 태스크에 역할(Role)을 부여
-   태스크 목록을 Broker로 전달

### 3. **Broker (중앙 라우터)**

-   각 Task에 적절한 Agent 선택
-   해당 Agent에 필요한 파라미터 보완
    -   부족하면 LLM 사용 or 유저 재질문
-   Agent 실행 → 응답 수집 → Orchestrator에 전달

### 4. **Agent (기능 단위 모듈)**

-   특정 역할 수행 (예: `tool-use`, `function-call`, `CoT`, `react_agent` 등)
-   필요시 브로커를 통해 다른 Agent 호출

### 5. **Agent Registry**

-   Redis 기반 동적 Agent 등록 시스템
-   Agent가 역할(Role), ParamSpec, API 정보를 등록
-   TTL 기반으로 헬스 체크 / 자동 제거

### 6. **LLM Client**

-   다양한 모델(OpenAI, Claude, local 등) 호출을 추상화
-   `LiteLLM` 등으로 호환성 확보

### 7. **Queue/Message Broker**

-   RabbitMQ 사용
-   Orchestrator ↔ Broker ↔ Agent 간 비동기 메시징 처리

---

## 아키텍처 다이어그램

<img width="531" alt="스크린샷 2025-04-17 오전 3 59 07" src="https://github.com/user-attachments/assets/f81819dc-5246-43ed-9cc7-29148a134aa9" />

---

## 전체 요청 흐름 요약

1. **Client → Orchestrator**:  
   `"마케팅 최신 동향 보고서 써줘"` 자연어 요청

2. **Orchestrator → Broker**:  
   Task로 분해

    - `web_search(marketing trend)`
    - `write_report(content=검색결과)`

3. **Broker → Registry**: 역할에 맞는 Agent 찾기

4. **Broker → Agent**: 적절한 Agent에게 Task 전달

    - Param 부족 시 LLM 또는 유저에게 요청

5. **Agent → Broker → Orchestrator**: 결과 반환

6. **Orchestrator → Client**: 최종 응답 전송

---

## 컴포넌트별 역할 요약

| 컴포넌트     | 주요 역할                                |
| ------------ | ---------------------------------------- |
| Client       | 자연어 요청, 재질문 응답                 |
| Orchestrator | 태스크 분해, 역할 할당                   |
| Broker       | 라우팅, 파라미터 보완, Task 실행         |
| Agent        | 기능 수행, 일부는 재귀 호출 가능 (ReAct) |
| Registry     | Agent role 목록 관리 (Redis 기반)        |
| LLM Client   | 다양한 모델 호출 통일                    |
| RabbitMQ     | Task 메시지 처리                         |

---

## Agent 등록/관리 구조

-   Agent는 실행 시 `POST /register`로 Registry에 정보 등록
-   등록 정보:
    -   `id`
    -   `role`
    -   `description`
    -   `params`: 필요한 입력 명세
    -   `type`
-   TTL(예: 30초) 부여 → 지속적인 heartbeat or 재등록 필요
-   삭제는 TTL 만료 or 수동 삭제

---

## 유연성 고려 사항

-   ✅ Agent는 동적으로 추가/삭제 가능
-   ✅ 파라미터 부족 시 LLM or 유저 fallback 전략
-   ✅ 역할(Roles) 존재 여부 기반 graceful degradation
-   ✅ Agent가 다른 Agent 호출 가능 (ReAct 구조)

---

## 기술 스택

| 기능           | 추천 기술                                     |
| -------------- | --------------------------------------------- |
| API 서버       | FastAPI                                       |
| 메시지 브로커  | RabbitMQ                                      |
| 동기/상태 저장 | Redis                                         |
| LLM 통합       | [LiteLLM](https://github.com/BerriAI/litellm) |
| 컨테이너화     | Docker + Docker Compose                       |
| Agent 관리     | 자체 구현 (FastAPI + Redis TTL 기반)          |

---
