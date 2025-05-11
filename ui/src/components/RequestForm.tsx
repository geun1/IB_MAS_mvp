import React, { useState, useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "react-query";
import { orchestratorApi } from "../api/orchestrator";
import { QueryRequest, QueryResponse } from "../types";
import ReactMarkdown from "react-markdown";
import ProcessMessage from "./ProcessMessage";
import {
    Message,
    ProcessMessage as ProcessMessageType,
    TaskInfo,
    ConversationStatus,
} from "../types/messages";
import { eventEmitter } from "../utils/eventEmitter";

interface RequestFormProps {
    onTaskCreated: (taskId: string) => void;
}

// 태스크 그룹화 인터페이스
interface TaskGroup {
    index: number;
    description: string;
    role: string;
    tasks: TaskInfo[];
}

// TaskDecompositionItem 타입 정의 추가
interface TaskDecompositionItem {
    description: string;
    role: string;
    index: number;
    level?: number;
}

// 대화 단위 상태 인터페이스
interface ConversationUnit {
    userMessage: Message; // 사용자 메시지
    systemResponses: {
        // 시스템 응답들
        taskDecomposition?: JSX.Element; // 태스크 분할 결과
        taskResults: JSX.Element[]; // 태스크 별 에이전트 결과들
        finalResponse?: Message; // 최종 응답
    };
}

// 폴링 상태 관리 인터페이스
interface PollingState {
    decompositionPolling: boolean;
    taskResultPolling: boolean;
    finalResultPolling: boolean;
}

// 개별 태스크 타입을 정의
interface TaskItem {
    id: string;
    status: string;
    role: string;
    description?: string;
    result?: any;
    index?: number;
    completed_at?: number;
    created_at?: number;
    message_id?: string; // 메시지 ID 추가
    task_id?: string; // 태스크 ID 추가
}

// 마크다운 테이블을 HTML로 변환
const convertMarkdownTablesToHtml = (content: string): string => {
    if (!content) return content;

    // 테이블 처리
    const tableRegex =
        /\|(.+)\|[\r\n]+\|([\s-:|]+)\|[\r\n]+((?:\|.+\|[\r\n]+)+)/g;

    return content.replace(
        tableRegex,
        (match, headerRow, separatorRow, bodyRows) => {
            try {
                // 헤더 처리
                const headers = headerRow
                    .split("|")
                    .map((cell: string) => cell.trim())
                    .filter(Boolean);

                // 본문 처리
                const rows = bodyRows.trim().split("\n");

                // HTML 테이블 생성
                let htmlTable =
                    '<div class="overflow-x-auto my-4 rounded-lg border border-gray-300 shadow">';
                htmlTable +=
                    '<table class="min-w-full border-collapse table-fixed">';

                // 헤더 추가
                htmlTable += '<thead class="bg-gray-100"><tr>';
                headers.forEach((header: string) => {
                    htmlTable += `<th class="border-b border-r last:border-r-0 border-gray-300 px-4 py-3 text-left font-semibold text-gray-700 text-sm">${header}</th>`;
                });
                htmlTable += "</tr></thead>";

                // 본문 추가
                htmlTable += '<tbody class="divide-y divide-gray-200">';
                rows.forEach((row: string) => {
                    if (row.trim()) {
                        const cells = row
                            .split("|")
                            .map((cell: string) => cell.trim())
                            .filter(Boolean);
                        htmlTable += '<tr class="hover:bg-gray-50">';
                        cells.forEach((cell: string) => {
                            // <br> 태그를 실제 줄바꿈으로 변환
                            const processedCell = cell.replace(
                                /<br>/g,
                                "<br/>"
                            );
                            htmlTable += `<td class="border-b border-r last:border-r-0 border-gray-300 px-4 py-3 text-gray-800 text-sm align-middle whitespace-pre-line">${processedCell}</td>`;
                        });
                        htmlTable += "</tr>";
                    }
                });
                htmlTable += "</tbody></table></div>";

                return htmlTable;
            } catch (e) {
                console.error("테이블 변환 오류:", e);
                return match; // 오류 발생 시 원본 반환
            }
        }
    );
};

// 결과에서 메시지 추출
const extractMessage = (data: any): string => {
    if (!data) return "";

    // console.log("응답 데이터 분석:", data); // 디버깅용 로깅

    // 여행 계획 에이전트의 ReAct 단계 정보가 있는 경우 특별히 처리
    if (data.steps_count && data.travel_plan) {
        // console.log("여행 계획 에이전트 ReAct 결과 감지");

        // 상세 단계 정보가 있는 경우 포맷팅
        let stepDetailsHtml = "";
        if (data.step_details && Array.isArray(data.step_details)) {
            stepDetailsHtml = "\n\n## ReAct 에이전트 처리 과정\n\n";

            // 단계별로 구분하여 표시
            data.step_details.forEach((step: any, index: number) => {
                const stepNum = index + 1;
                const stepType =
                    step.type === "reasoning"
                        ? "🧠 추론"
                        : step.type === "action"
                        ? "🛠️ 행동"
                        : step.type === "observation"
                        ? "👁️ 관찰"
                        : "⚠️ 오류";

                stepDetailsHtml += `### 단계 ${stepNum}: ${stepType}\n`;

                // 내용이 JSON 형태로 저장된 경우 파싱 시도
                let content = step.content;
                try {
                    if (
                        typeof content === "string" &&
                        content.startsWith("{")
                    ) {
                        const parsed = JSON.parse(content);

                        if (step.type === "reasoning") {
                            stepDetailsHtml += `**사고 과정**: ${
                                parsed.thought || ""
                            }\n\n`;
                            stepDetailsHtml += `**다음 행동**: ${
                                parsed.next_action || ""
                            }\n\n`;
                            if (parsed.params) {
                                stepDetailsHtml += `**파라미터**: \`\`\`json\n${JSON.stringify(
                                    parsed.params,
                                    null,
                                    2
                                )}\n\`\`\`\n\n`;
                            }
                            stepDetailsHtml += `**이유**: ${
                                parsed.reason || ""
                            }\n\n`;
                        } else {
                            // 다른 형태의 내용은 그대로 출력
                            stepDetailsHtml += `\`\`\`json\n${JSON.stringify(
                                parsed,
                                null,
                                2
                            )}\n\`\`\`\n\n`;
                        }
                    } else {
                        stepDetailsHtml += `${content}\n\n`;
                    }
                } catch (e) {
                    // 파싱 실패 시 원본 내용 그대로 표시
                    stepDetailsHtml += `${content}\n\n`;
                }
            });
        }

        // 여행 계획과 ReAct 단계 정보를 함께 반환
        return `
## 📝 최종 여행 계획

${data.travel_plan}

---

### 📊 ReAct 에이전트 처리 정보
* 총 단계 수: ${data.steps_count}회
* 추론-행동-관찰 루프 수행 완료

<details>
<summary>📋 상세 처리 과정 보기</summary>

${stepDetailsHtml}
</details>
`;
    }

    // 이전의 기존 로직 계속
    // 결과가 이미 문자열인 경우
    if (typeof data === "string") {
        // console.log("결과가 직접 문자열");
        return data;
    }

    // 직접 'message' 필드가 있고 내용이 있는 경우
    if (
        data.message &&
        data.message.trim() !== "처리가 완료되었으나 결과가 없습니다."
    ) {
        // console.log("최상위 message 필드 감지");
        return String(data.message);
    }

    // tasks 배열이 있는 경우
    if (data.tasks && Array.isArray(data.tasks) && data.tasks.length > 0) {
        // console.log("tasks 배열 감지");

        // 완료된 태스크 중에서 찾기
        const completedTasks = data.tasks.filter(
            (task: any) => task.status === "completed"
        );
        if (completedTasks.length > 0) {
            // 가장 마지막 완료된 태스크 사용
            const lastTask = completedTasks[completedTasks.length - 1];

            // 중첩된 결과 구조 확인
            if (lastTask.result) {
                // 구조: result > result > content
                if (lastTask.result.result && lastTask.result.result.content) {
                    // console.log("task.result.result.content 구조 감지");
                    return String(lastTask.result.result.content);
                }

                // 구조: result > message
                if (lastTask.result.message) {
                    // console.log("task.result.message 구조 감지");
                    return String(lastTask.result.message);
                }

                // 구조: result > content
                if (lastTask.result.content) {
                    // console.log("task.result.content 구조 감지");
                    return String(lastTask.result.content);
                }

                // 구조: result > result > message
                if (lastTask.result.result && lastTask.result.result.message) {
                    // console.log("task.result.result.message 구조 감지");
                    return String(lastTask.result.result.message);
                }

                // 구조: result가 직접 문자열인 경우
                if (typeof lastTask.result === "string") {
                    // console.log("task.result가 직접 문자열");
                    return lastTask.result;
                }

                // 구조: result가 객체이지만 다른 형태인 경우 JSON으로 반환
                if (typeof lastTask.result === "object") {
                    try {
                        // console.log("task.result가 객체, JSON으로 변환");
                        return JSON.stringify(lastTask.result, null, 2);
                    } catch (e) {
                        console.error("JSON 변환 오류:", e);
                    }
                }
            }
        }
    }

    // 결과가 중첩된 구조인 경우 (result.result.message/content)
    if (data.result && typeof data.result === "object" && data.result.result) {
        // console.log("result.result 구조 감지");
        if (data.result.result.content) {
            // console.log("result.result.content 감지");
            return String(data.result.result.content);
        }
        if (data.result.result.message) {
            // console.log("result.result.message 감지");
            return String(data.result.result.message);
        }
        return "";
    }

    // 단일 수준 구조인 경우 (result.message/content)
    if (data.result && typeof data.result === "object") {
        // console.log("result 객체 구조 감지");
        if (data.result.content) {
            // console.log("result.content 감지");
            return String(data.result.content);
        }
        if (data.result.message) {
            // console.log("result.message 감지");
            return String(data.result.message);
        }

        // 결과가 있지만 예상 구조가 아닌 경우 JSON으로 변환
        try {
            // console.log("result가 비표준 구조, JSON으로 변환");
            return JSON.stringify(data.result, null, 2);
        } catch (e) {
            console.error("JSON 변환 오류:", e);
        }
    }

    // 아무것도 찾지 못했지만 데이터가 있는 경우
    if (data) {
        try {
            // console.log("비표준 데이터 구조, 전체를 JSON으로 변환");
            return JSON.stringify(data, null, 2);
        } catch (e) {
            console.error("JSON 변환 오류:", e);
        }
    }

    // 직접 message 필드가 있는 경우 (추가 검사)
    if (data.message) {
        return String(data.message);
    }

    return "처리가 완료되었으나 결과가 없습니다.";
};

// 고유한 대화 ID 생성 함수
function generateConversationId(): string {
    return (
        Math.random().toString(36).substring(2, 15) +
        Math.random().toString(36).substring(2, 15)
    );
}

// 고유한 메시지 ID 생성 함수 추가
function generateMessageId(): string {
    return (
        "msg-" +
        Math.random().toString(36).substring(2, 10) +
        Date.now().toString(36)
    );
}

// 로딩 상태 메시지 컴포넌트 추가
const LoadingMessage: React.FC<{
    type: "decomposition" | "agent" | "integration";
}> = ({ type }) => {
    const getMessage = () => {
        switch (type) {
            case "decomposition":
                return "태스크 분해 중...";
            case "agent":
                return "에이전트 작업 처리 중...";
            case "integration":
                return "최종 결과 생성 중...";
        }
    };

    const getIcon = () => {
        return (
            <svg
                className="animate-spin -ml-1 mr-2 h-4 w-4 text-blue-500"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
            >
                <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                ></circle>
                <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
            </svg>
        );
    };

    return (
        <div className="flex items-center text-blue-500 font-medium px-3 py-2 bg-blue-50 rounded-md shadow-sm border border-blue-100 mb-2">
            {getIcon()}
            {getMessage()}
        </div>
    );
};

const RequestForm: React.FC<RequestFormProps> = ({ onTaskCreated }) => {
    const [query, setQuery] = useState("");
    const [messages, setMessages] = useState<Message[]>([]); // 사용자 메시지만 저장
    const [currentConversationUnit, setCurrentConversationUnit] =
        useState<ConversationUnit | null>(null); // 현재 진행 중인 대화 단위
    const [completedUnits, setCompletedUnits] = useState<ConversationUnit[]>(
        []
    ); // 완료된 대화 단위들
    const [conversationId, setConversationId] = useState<string | null>(null);
    const [currentMessageId, setCurrentMessageId] = useState<string | null>(
        null
    ); // 현재 메시지 ID 추가
    const [waitingForResponse, setWaitingForResponse] = useState(false);
    const [showConversationList, setShowConversationList] = useState(false);
    // 자동 스크롤 제어 상태 추가
    const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);
    const [responseCompleted, setResponseCompleted] = useState(false);

    // 각 단계별 폴링 상태
    const [pollingState, setPollingState] = useState<PollingState>({
        decompositionPolling: false,
        taskResultPolling: false,
        finalResultPolling: false,
    });

    // 태스크 분리 결과 저장
    const [taskDecomposition, setTaskDecomposition] = useState<any>(null); // 태스크 분해 결과
    const [completedTaskIds, setCompletedTaskIds] = useState<Set<string>>(
        new Set()
    ); // 완료된 태스크 ID 목록
    const [taskIds, setTaskIds] = useState<string[]>([]); // 태스크 ID 목록
    const [expectedAgentTasks, setExpectedAgentTasks] = useState<number>(0); // 예상되는 에이전트 태스크 개수

    const queryClient = useQueryClient();
    const scrollRef = useRef<HTMLDivElement>(null);

    // useMutation 정의 (타입 명시)
    const queryMutation = useMutation<QueryResponse, Error, QueryRequest>(
        (request: QueryRequest) => orchestratorApi.processQuery(request),
        {
            onSuccess: (data) => {
                console.log("쿼리 요청 성공:", data);

                // conversation_id가 있는 경우
                if (data.conversation_id) {
                    console.log(`[쿼리] 대화 ID 설정: ${data.conversation_id}`);
                    setConversationId(data.conversation_id);

                    // 서버에서 반환된 message_id가 있고 현재와 다른 경우 업데이트
                    if (
                        data.message_id &&
                        data.message_id !== currentMessageId
                    ) {
                        // console.log(
                        //     `[쿼리] 서버의 메시지 ID로 업데이트: ${data.message_id} (이전: ${currentMessageId})`
                        // );
                        setCurrentMessageId(data.message_id);
                    } else if (
                        data.message_id &&
                        data.message_id === currentMessageId
                    ) {
                        // console.log(
                        //     `[쿼리] 서버에서 동일한 메시지 ID 확인: ${currentMessageId}`
                        // );
                    } else if (!data.message_id && currentMessageId) {
                        // console.log(
                        //     `[쿼리] 서버에서 메시지 ID가 반환되지 않음, 클라이언트 ID 유지: ${currentMessageId}`
                        // );
                    } else {
                        // console.warn(
                        //     "[쿼리] 메시지 ID가 없음: 서버와 클라이언트 모두에 없음"
                        // );
                        setWaitingForResponse(false);
                        return;
                    }

                    // 메시지 ID를 확실히 확인한 후 계속 진행
                    // console.log(
                    //     `[쿼리] 최종 사용 메시지 ID: ${currentMessageId}`
                    // );

                    // 이미 폴링이 시작된 경우 중복 시작 방지
                    if (!pollingState.decompositionPolling) {
                        // console.log(
                        //     `[쿼리] 태스크 분해 폴링 시작 (메시지 ID: ${currentMessageId})`
                        // );
                        setPollingState({
                            decompositionPolling: true,
                            taskResultPolling: false,
                            finalResultPolling: false,
                        });
                    }
                } else {
                    console.warn("[쿼리] 응답에 대화 ID가 없음!");
                    setWaitingForResponse(false);
                }
            },
            onError: (error) => {
                console.error("쿼리 요청 실패:", error);
                setWaitingForResponse(false);
                // 폴링 중지
                setPollingState({
                    decompositionPolling: false,
                    taskResultPolling: false,
                    finalResultPolling: false,
                });
            },
        }
    );

    // 태스크 분해 결과 폴링 쿼리
    const { data: decompositionData, refetch: refetchDecomposition } = useQuery(
        ["taskDecomposition", conversationId, currentMessageId], // 메시지 ID 추가
        async () => {
            // 대화 ID와 메시지 ID 모두 필수!
            if (!conversationId) throw new Error("대화 ID가 없습니다");
            if (!currentMessageId) throw new Error("메시지 ID가 없습니다");

            // console.log(
            //     `[태스크 분리] 폴링 시도: 대화=${conversationId}, 메시지=${currentMessageId}`
            // );

            // 반드시 메시지 ID로 요청
            try {
                // console.log(
                //     `[태스크 분리] 메시지 ID로 요청: ${currentMessageId}`
                // );
                const response = await orchestratorApi.getTaskDecomposition(
                    conversationId,
                    currentMessageId
                );

                // console.log(`[태스크 분리] 응답:`, response);

                // 응답에서 메시지 ID 확인 - 추가 검증
                if (
                    response.message_id &&
                    response.message_id !== currentMessageId
                ) {
                    // console.warn(
                    //     `[태스크 분리] 응답 메시지 ID(${response.message_id})가 요청 메시지 ID(${currentMessageId})와 다릅니다.`
                    // );
                    // 응답을 재구성하고 현재 메시지 ID 강제 설정
                    response.message_id = currentMessageId;
                }

                // 에러 응답 체크
                if (response.error) {
                    // console.error(`[태스크 분리] 에러 응답: ${response.error}`);
                    // 폴링을 계속하기 위해 데이터 형식은 유지하되 에러 정보 포함
                    return {
                        conversation_id: conversationId,
                        message_id: currentMessageId,
                        task_descriptions: [],
                        execution_levels: [],
                        error: response.error,
                        retry: true, // 재시도 플래그
                    };
                }

                return response;
            } catch (error) {
                // console.error(`[태스크 분리] 요청 실패:`, error);
                // 폴링을 계속하기 위해 데이터 형식은 유지
                return {
                    conversation_id: conversationId,
                    message_id: currentMessageId,
                    task_descriptions: [],
                    execution_levels: [],
                    error: `API 요청 실패: ${error}`,
                    retry: true, // 재시도 플래그
                };
            }
        },
        {
            enabled: (() => {
                // 현재 데이터가 _pollingDisabled 상태인지 확인
                const currentData = queryClient.getQueryData([
                    "taskDecomposition",
                    conversationId,
                    currentMessageId,
                ]);
                const isDisabled =
                    currentData &&
                    (currentData as any)._pollingDisabled === true;

                // 기본 활성화 조건과 함께 _pollingDisabled가 아닐 때만 활성화
                return (
                    !!conversationId &&
                    !!currentMessageId &&
                    pollingState.decompositionPolling &&
                    !isDisabled
                );
            })(),
            refetchInterval: pollingState.decompositionPolling ? 3000 : false, // 3초마다 폴링
            refetchIntervalInBackground: true,
            refetchOnWindowFocus: false,
            retry: 10, // 최대 10번 재시도
            retryDelay: (attemptIndex) =>
                Math.min(1000 * 2 ** attemptIndex, 10000), // 지수 백오프 전략
            onError: (error) => {
                console.error("[태스크 분리] 폴링 오류:", error);
            },
        }
    );

    // 에이전트 태스크 결과 폴링 쿼리
    const { data: agentTasksData, refetch: refetchAgentTasks } = useQuery(
        ["agentTasks", conversationId, currentMessageId],
        async () => {
            // 대화 ID와 메시지 ID 확인
            if (!conversationId) throw new Error("대화 ID가 없습니다");
            if (!currentMessageId) throw new Error("메시지 ID가 없습니다");

            // console.log(
            //     `[에이전트 결과] 폴링 시도: 대화=${conversationId}, 메시지=${currentMessageId}`
            // );

            try {
                const response = await orchestratorApi.getAgentTasks(
                    conversationId,
                    currentMessageId
                );

                // console.log(`[에이전트 결과] 응답:`, response);

                // 응답에서 메시지 ID 확인 - 추가 검증
                if (
                    response.message_id &&
                    response.message_id !== currentMessageId
                ) {
                    // console.warn(
                    //     `[에이전트 결과] 응답 메시지 ID(${response.message_id})가 요청 메시지 ID(${currentMessageId})와 다릅니다.`
                    // );
                    // 응답을 재구성하고 현재 메시지 ID 강제 설정
                    response.message_id = currentMessageId;

                    // 에이전트 태스크에 메시지 ID 설정
                    if (response.tasks && Array.isArray(response.tasks)) {
                        response.tasks = response.tasks.map((task: any) => ({
                            ...task,
                            message_id: currentMessageId,
                        }));
                    }
                }

                // 에러 응답 체크
                if (response.error) {
                    // console.error(
                    //     `[에이전트 결과] 에러 응답: ${response.error}`
                    // );
                    return {
                        conversation_id: conversationId,
                        message_id: currentMessageId,
                        tasks: [],
                        error: response.error,
                        retry: true, // 재시도 플래그
                    };
                }

                return response;
            } catch (error) {
                // console.error(`[에이전트 결과] 요청 실패:`, error);
                return {
                    conversation_id: conversationId,
                    message_id: currentMessageId,
                    tasks: [],
                    error: `API 요청 실패: ${error}`,
                    retry: true, // 재시도 플래그
                };
            }
        },
        {
            enabled: (() => {
                // 현재 데이터가 _pollingDisabled 상태인지 확인
                const currentData = queryClient.getQueryData([
                    "agentTasks",
                    conversationId,
                    currentMessageId,
                ]);
                const isDisabled =
                    currentData &&
                    (currentData as any)._pollingDisabled === true;

                // 기본 활성화 조건과 함께 _pollingDisabled가 아닐 때만 활성화
                return (
                    !!conversationId &&
                    !!currentMessageId &&
                    pollingState.taskResultPolling &&
                    !isDisabled
                );
            })(),
            refetchInterval: pollingState.taskResultPolling ? 3000 : false, // 3초마다 폴링
            refetchIntervalInBackground: true,
            refetchOnWindowFocus: false,
            retry: 10, // 최대 10번 재시도
            retryDelay: (attemptIndex) =>
                Math.min(1000 * 2 ** attemptIndex, 10000), // 지수 백오프 전략
            onError: (error) => {
                console.error("[에이전트 결과] 폴링 오류:", error);
            },
        }
    );

    // 최종 결과 폴링 쿼리
    const { data: finalResultData, refetch: refetchFinalResult } = useQuery(
        ["finalResult", conversationId, currentMessageId],
        async () => {
            // 대화 ID와 메시지 ID 확인
            if (!conversationId) throw new Error("대화 ID가 없습니다");
            if (!currentMessageId) throw new Error("메시지 ID가 없습니다");

            // console.log(
            //     `[최종 결과] 폴링 시도: 대화=${conversationId}, 메시지=${currentMessageId}`
            // );

            try {
                // 이미 완료된 상태인지 확인
                const cachedData = queryClient.getQueryData([
                    "finalResult",
                    conversationId,
                    currentMessageId,
                ]);

                if (cachedData && (cachedData as any)._forceStopped) {
                    // console.log(
                    //     "[최종 결과] 폴링 강제 중단됨 - 캐시된 데이터 사용"
                    // );
                    return cachedData;
                }

                const response = await orchestratorApi.getFinalResult(
                    conversationId,
                    currentMessageId
                );

                console.log(`[최종 결과] 응답:`, response);

                // 응답에서 메시지 ID 확인 - 추가 검증
                if (
                    response.message_id &&
                    response.message_id !== currentMessageId
                ) {
                    // console.warn(
                    //     `[최종 결과] 응답 메시지 ID(${response.message_id})가 요청 메시지 ID(${currentMessageId})와 다릅니다.`
                    // );
                    // 응답을 재구성하고 현재 메시지 ID 강제 설정
                    response.message_id = currentMessageId;
                }

                // 에러 응답 체크
                if (response.error) {
                    console.error(`[최종 결과] 에러 응답: ${response.error}`);
                    return {
                        conversation_id: conversationId,
                        message_id: currentMessageId,
                        error: response.error,
                        retry: true, // 재시도 플래그
                    };
                }

                // message 또는 completed 상태인 경우 폴링 강제 중단 표시
                if (response.message || response.status === "completed") {
                    // console.log(
                    //     "[최종 결과] 성공 응답 감지 - 폴링 강제 중단 설정"
                    // );
                    response._forceStopped = true;

                    // 전역 상태 업데이트 - 비동기 효과를 기다리지 않고 즉시 적용
                    window.setTimeout(() => {
                        // console.log("[최종 결과] 폴링 상태 강제 업데이트");
                        queryClient.setQueryData(
                            ["finalResult", conversationId, currentMessageId],
                            (oldData: any) => ({
                                ...response,
                                _forceStopped: true,
                                _pollingDisabled: true,
                            })
                        );

                        // 전체 폴링 상태 초기화
                        setPollingState({
                            decompositionPolling: false,
                            taskResultPolling: false,
                            finalResultPolling: false,
                        });

                        // 명시적 쿼리 취소
                        queryClient.cancelQueries(
                            ["finalResult", conversationId, currentMessageId],
                            { exact: true }
                        );
                    }, 0);
                }

                return response;
            } catch (error) {
                console.error(`[최종 결과] 요청 실패:`, error);
                return {
                    conversation_id: conversationId,
                    message_id: currentMessageId,
                    error: `API 요청 실패: ${error}`,
                    retry: true, // 재시도 플래그
                };
            }
        },
        {
            enabled: (() => {
                // 현재 데이터가 _pollingDisabled 상태인지 확인
                const currentData = queryClient.getQueryData([
                    "finalResult",
                    conversationId,
                    currentMessageId,
                ]);

                const isDisabled =
                    currentData &&
                    ((currentData as any)._pollingDisabled === true ||
                        (currentData as any)._forceStopped === true);

                const result =
                    !!conversationId &&
                    !!currentMessageId &&
                    pollingState.finalResultPolling &&
                    !isDisabled;

                console.log(
                    `[최종 결과] 폴링 활성화 상태: ${result}, 강제중단: ${isDisabled}`
                );

                // 기본 활성화 조건과 함께 _pollingDisabled나 _forceStopped가 아닐 때만 활성화
                return result;
            })(),
            refetchInterval: pollingState.finalResultPolling ? 3000 : false, // 3초마다 폴링
            refetchIntervalInBackground: true,
            refetchOnWindowFocus: false,
            retry: 10, // 최대 10번 재시도
            retryDelay: (attemptIndex) =>
                Math.min(1000 * 2 ** attemptIndex, 10000), // 지수 백오프 전략
            onError: (error) => {
                console.error("[최종 결과] 폴링 오류:", error);
            },
        }
    );

    // 대화 목록 조회
    const {
        data: conversations,
        isLoading: isConversationsLoading,
        refetch: refetchConversations,
    } = useQuery("conversations", orchestratorApi.listConversations, {
        refetchInterval: 30000, // 30초마다 대화 목록 업데이트
        enabled: showConversationList, // 대화 목록이 보여질 때만 활성화
        staleTime: 10000, // 10초 동안은 캐시 데이터 사용
    });

    // 선택한 대화의 메시지 조회
    const loadConversationMessages = async (selectedConvId: string) => {
        try {
            setWaitingForResponse(true);

            // 대화 정보 조회
            const detail = await orchestratorApi.getConversationDetail(
                selectedConvId
            );

            // 대화에 속한 메시지 목록 조회
            const messages = await orchestratorApi.getConversationMessages(
                selectedConvId
            );

            // conversationId 설정
            setConversationId(selectedConvId);

            // 이전 대화 내용 초기화
            setCompletedUnits([]);
            setCurrentConversationUnit(null);

            // 메시지가 있는 경우 대화 단위로 변환하여 표시
            if (messages && messages.length > 0) {
                const units: ConversationUnit[] = [];

                messages.forEach((message: any, index: number) => {
                    // 사용자 메시지 변환
                    const userMessage: Message = {
                        role: "user",
                        content: message.request || "",
                        timestamp: new Date(
                            message.created_at
                                ? message.created_at * 1000
                                : Date.now()
                        ),
                        conversationId: selectedConvId,
                    };

                    // 시스템 응답 구성
                    const finalResponse: Message | undefined = message.response
                        ? {
                              role: "assistant",
                              content: message.response,
                              timestamp: new Date(
                                  message.updated_at
                                      ? message.updated_at * 1000
                                      : Date.now()
                              ),
                              conversationId: selectedConvId,
                              finalResult: true,
                          }
                        : undefined;

                    // 대화 단위 구성
                    const unit: ConversationUnit = {
                        userMessage,
                        systemResponses: {
                            taskResults: [],
                            finalResponse,
                        },
                    };

                    units.push(unit);
                });

                // 마지막 메시지를 제외한 모든 메시지를 완료된 단위로 설정
                if (units.length > 1) {
                    setCompletedUnits(units.slice(0, units.length - 1));
                    setCurrentConversationUnit(units[units.length - 1]);
                } else if (units.length === 1) {
                    setCurrentConversationUnit(units[0]);
                }
            }

            setWaitingForResponse(false);
            setShowConversationList(false); // 대화 선택 후 목록 닫기
        } catch (error) {
            console.error("대화 로드 오류:", error);
            setWaitingForResponse(false);
        }
    };

    // useEffect를 사용하여 폴링 상태 변경 시 적절한 refetch 트리거
    useEffect(() => {
        // conversationId가 없으면 아무 작업도 수행하지 않음
        if (!conversationId) return;

        // console.log(
        //     `[폴링 상태 변경] 대화 ID: ${conversationId}, 메시지 ID: ${
        //         currentMessageId || "없음"
        //     }`
        // );
        // console.log(
        //     `[폴링 상태] 분해: ${pollingState.decompositionPolling}, 태스크: ${pollingState.taskResultPolling}, 최종: ${pollingState.finalResultPolling}`
        // );

        if (pollingState.decompositionPolling && refetchDecomposition) {
            // 태스크 분리 결과 폴링 시작
            // console.log("[폴링] 태스크 분리 폴링 시작");
            refetchDecomposition();
        } else if (pollingState.taskResultPolling && refetchAgentTasks) {
            // 에이전트 태스크 결과 폴링 시작
            // console.log("[폴링] 에이전트 태스크 결과 폴링 시작");
            refetchAgentTasks();
        } else if (pollingState.finalResultPolling && refetchFinalResult) {
            // 최종 결과 폴링 시작
            // console.log("[폴링] 최종 결과 폴링 시작");
            refetchFinalResult();
        }
    }, [
        conversationId,
        currentMessageId,
        pollingState.decompositionPolling,
        pollingState.taskResultPolling,
        pollingState.finalResultPolling,
        refetchDecomposition,
        refetchAgentTasks,
        refetchFinalResult,
    ]);

    // 태스크 분해 결과 처리 useEffect
    useEffect(() => {
        // 데이터가 없으면 처리하지 않음
        if (!decompositionData) {
            console.log("[태스크 분해] 응답 데이터 없음");
            return;
        }

        console.log("[태스크 분해] 응답 데이터:", decompositionData);
        console.log(
            "[태스크 분해] JSON:",
            JSON.stringify(decompositionData, null, 2)
        );

        // 응답에서 메시지 ID와 대화 ID 확인
        const responseMessageId = decompositionData.message_id || "";
        const responseConversationId = decompositionData.conversation_id || "";

        // 응답 메시지 ID가 현재 추적 중인 메시지 ID와 다른 경우 무시
        if (
            responseMessageId &&
            currentMessageId &&
            responseMessageId !== currentMessageId
        ) {
            console.log(
                `[태스크 분해] 다른 메시지의 응답이 도착했습니다. 현재: ${currentMessageId}, 응답: ${responseMessageId}. 무시합니다.`
            );
            return;
        }

        // 응답 대화 ID가 현재 추적 중인 대화 ID와 다른 경우 무시
        if (
            responseConversationId &&
            conversationId &&
            responseConversationId !== conversationId
        ) {
            console.log(
                `[태스크 분해] 다른 대화의 응답이 도착했습니다. 현재: ${conversationId}, 응답: ${responseConversationId}. 무시합니다.`
            );
            return;
        }

        // 응답에서 메시지 ID 확인 및 업데이트
        if (
            decompositionData.message_id &&
            (!currentMessageId ||
                currentMessageId !== decompositionData.message_id)
        ) {
            console.log(
                `[태스크 분해] 응답에서 메시지 ID 업데이트: ${decompositionData.message_id}`
            );
            setCurrentMessageId(decompositionData.message_id);
        }

        // 메시지 ID 확인 - 이미 위에서 업데이트했으므로 여기서는 확인 용도로만 사용
        // console.log(
        //     `[태스크 분해] 응답 메시지 ID: ${responseMessageId}, 현재 메시지 ID: ${
        //         currentMessageId || "없음"
        //     }`
        // );

        // 에러 응답이면 계속 폴링하도록 처리
        if (decompositionData.error) {
            // console.log(
            //     `[태스크 분해] 에러 응답 수신: ${decompositionData.error}, 폴링 계속`
            // );
            return; // 폴링 계속
        }

        // 태스크 분해 결과가 없으면 계속 폴링
        if (
            !decompositionData.task_descriptions ||
            decompositionData.task_descriptions.length === 0
        ) {
            // console.log(`[태스크 분해] 태스크 결과 없음, 폴링 계속`);
            return; // 폴링 계속
        }

        // 여기까지 왔다면 성공적으로 결과가 도착한 것이므로 태스크 분해 폴링 중단
        // console.log(
        //     `[태스크 분해] 성공적으로 결과 수신, 태스크 분해 폴링 중단`
        // );

        // 폴링 상태 변경
        setPollingState((prev) => ({
            ...prev,
            decompositionPolling: false, // 태스크 분해 폴링 중단
        }));

        // React Query 폴링 명시적 중단 - 쿼리 비활성화
        queryClient.setQueryData(
            ["taskDecomposition", conversationId, currentMessageId],
            (oldData: any) => ({ ...oldData, _pollingDisabled: true })
        );
        queryClient.cancelQueries([
            "taskDecomposition",
            conversationId,
            currentMessageId,
        ]);

        // 태스크 분해 결과 저장 (형식에 상관없이 저장)
        setTaskDecomposition(decompositionData);

        // 태스크 ID 목록 추출 및 예상되는 에이전트 태스크 개수 계산
        let allTasks: string[] = [];
        let expectedTasks = 0;

        if (Array.isArray(decompositionData.task_descriptions[0])) {
            // 2차원 배열인 경우
            decompositionData.task_descriptions.forEach(
                (levelTasks: string[], levelIndex: number) => {
                    levelTasks.forEach((task: string, taskIndex: number) => {
                        allTasks.push(`task_${levelIndex}_${taskIndex}`);
                        expectedTasks++;
                    });
                }
            );
        } else {
            // 1차원 배열인 경우
            allTasks = decompositionData.task_descriptions.map(
                (_: string, index: number) => `task_${index}`
            );
            expectedTasks = decompositionData.task_descriptions.length;
        }

        console.log(
            `[태스크 분해] 예상되는 에이전트 태스크 개수: ${expectedTasks}`
        );
        setExpectedAgentTasks(expectedTasks);

        console.log("[태스크 분해] 태스크 ID 목록:", allTasks);
        setTaskIds(allTasks);

        // 태스크 분해 결과 즉시 렌더링 (형식에 상관없이 시도)
        const success = updateTaskDecomposition(decompositionData);
        console.log("[태스크 분해] 렌더링 성공 여부:", success);

        // 태스크 분해가 완료되면 태스크 결과 폴링 시작 (여기서 다음 단계로 진행)
        const timeoutId = setTimeout(() => {
            // 메시지 ID가 있는지 다시 확인
            if (!currentMessageId && decompositionData.message_id) {
                console.log(
                    `[태스크 분해] 메시지 ID 설정: ${decompositionData.message_id}`
                );
                setCurrentMessageId(decompositionData.message_id);
            }

            // 메시지 ID 유효성 확인 후 진행
            if (currentMessageId || decompositionData.message_id) {
                console.log(
                    `[시퀀스] 태스크 분해 완료, 메시지 ID=${
                        currentMessageId || decompositionData.message_id
                    }로 에이전트 태스크 결과 폴링 시작`
                );
                setPollingState({
                    decompositionPolling: false, // 태스크 분해 폴링 중단
                    taskResultPolling: true, // 태스크 결과 폴링 시작
                    finalResultPolling: false,
                });
            } else {
                console.error(
                    "[시퀀스] 유효한 메시지 ID가 없어 태스크 결과 폴링을 시작할 수 없습니다"
                );
            }
        }, 2000);

        return () => {
            // 컴포넌트 언마운트 또는 디펜던시 변경 시 타이머 정리
            clearTimeout(timeoutId);
        };
    }, [decompositionData, currentMessageId, conversationId, queryClient]);

    // 태스크 처리 상태 초기화 함수 추가
    const resetProcessingState = () => {
        console.log("[상태 초기화] 태스크 처리 상태 초기화");
        // 태스크 분해 관련 상태 초기화
        setTaskDecomposition(null);
        setCompletedTaskIds(new Set());
        setTaskIds([]);
        setExpectedAgentTasks(0);

        // React Query 캐시 전체 초기화 (주의: conversation 관련 캐시는 유지)
        queryClient.removeQueries({
            predicate: (query) => {
                // query.queryKey를 문자열 배열로 캐스팅
                const key = query.queryKey as string[];
                // conversation 관련 쿼리만 유지하고 나머지 제거
                return (
                    key[0] !== "conversations" &&
                    !key[0].startsWith("conversation_details")
                );
            },
        });
    };

    // 태스크 결과 업데이트 함수
    const updateTaskResult = (task: TaskItem) => {
        if (!task) {
            console.error("[태스크 결과] 유효하지 않은 태스크:", task);
            return;
        }

        // 태스크에 role이 없는 경우 처리하지 않음
        if (!task.role) {
            console.warn("[태스크 결과] 역할이 없는 태스크:", task);
            return;
        }

        // task_id 확인 - 연관된 메시지 ID가 있는지 확인
        if (
            task.message_id &&
            currentMessageId &&
            task.message_id !== currentMessageId
        ) {
            console.log(
                `[태스크 결과] 다른 메시지의 태스크입니다. 현재: ${currentMessageId}, 태스크: ${task.message_id}. 무시합니다.`
            );
            return;
        }

        // taskId를 id 또는 index 값에서 가져옴
        const taskId =
            task.id ||
            task.task_id ||
            task.index?.toString() ||
            Math.random().toString(36).substring(7);

        setCurrentConversationUnit((prev) => {
            if (!prev) {
                console.error("[태스크 결과] 현재 대화 단위가 없습니다");
                return null;
            }

            const updatedUnit = { ...prev };

            // 결과 내용 처리 (객체일 경우 문자열로 변환)
            let resultContent = task.result
                ? typeof task.result === "object"
                    ? JSON.stringify(task.result, null, 2)
                    : String(task.result)
                : "결과 없음";

            // messageId가 null인 경우 undefined로 변환 (타입 오류 수정)
            const messageIdForProps =
                task.message_id || currentMessageId || undefined;

            // 처리 단계 타입 정의 추가
            interface ReactStep {
                type: string;
                content: string;
                timestamp?: number;
            }

            // Travel Planner 에이전트 결과 특별 처리 (ReAct 에이전트)
            let taskElement;
            if (
                task.role === "travel_planner" &&
                task.result &&
                task.result.steps_count
            ) {
                // ReAct 에이전트로 처리
                console.log(
                    "[ReAct 에이전트] 여행 계획 에이전트 결과 처리:",
                    task.result
                );

                // steps_count를 사용해 ReAct 단계 정보 구성
                const stepsCount = task.result.steps_count || 0;

                // 각 단계의 비율을 계산 (실제 ReAct 구현의 단계별 비율에 맞게 조정)
                const reasoningSteps = Math.floor(stepsCount / 3);
                const actionSteps = Math.floor(stepsCount / 3);
                const observationSteps =
                    stepsCount - reasoningSteps - actionSteps;

                // 결과 콘텐츠에서 여행 계획만 추출
                let travelPlanContent =
                    task.result.travel_plan || resultContent;

                // 단계별 내용이 있으면 추가
                if (
                    task.result.step_details &&
                    Array.isArray(task.result.step_details)
                ) {
                    // 단계별 요약 정보 추가
                    travelPlanContent +=
                        "\n\n## 📊 ReAct 에이전트 처리 과정 요약\n\n";
                    travelPlanContent += `총 단계 수: ${stepsCount}회\n`;
                    travelPlanContent += `추론 단계: ${reasoningSteps}회 | 행동 단계: ${actionSteps}회 | 관찰 단계: ${observationSteps}회\n\n`;

                    // 다른 에이전트 호출 정보 확인 및 추가
                    const actionStepsList = task.result.step_details.filter(
                        (step: ReactStep) => step.type === "action"
                    );

                    const agentCalls = new Set<string>();
                    actionStepsList.forEach((step: ReactStep) => {
                        if (step.content && typeof step.content === "string") {
                            // 행동 단계에서 에이전트 호출 정보 추출 시도
                            if (
                                step.content.includes("web_search") ||
                                step.content.includes("writer") ||
                                step.content.includes("data_analyzer")
                            ) {
                                // 간단한 정규식으로 에이전트 이름 추출
                                const matches =
                                    step.content.match(/행동: ([a-z_]+)/i);
                                if (matches && matches[1]) {
                                    agentCalls.add(matches[1]);
                                }
                            }
                        }
                    });

                    if (agentCalls.size > 0) {
                        travelPlanContent += "### 🤝 협업한 에이전트\n";
                        agentCalls.forEach((agent) => {
                            travelPlanContent += `- ${agent}\n`;
                        });
                        travelPlanContent += "\n";
                    }

                    // 세부 단계 표시는 접을 수 있는 형태로 변경
                    travelPlanContent +=
                        "<details>\n<summary>📋 세부 단계 진행 과정 보기</summary>\n\n";

                    task.result.step_details.forEach(
                        (step: ReactStep, idx: number) => {
                            if (step.type === "reasoning") {
                                travelPlanContent += `### 단계 ${
                                    idx + 1
                                } - 🧠 추론\n${step.content}\n\n`;
                            } else if (step.type === "action") {
                                travelPlanContent += `### 단계 ${
                                    idx + 1
                                } - 🛠️ 행동\n\`\`\`\n${
                                    step.content
                                }\n\`\`\`\n\n`;
                            } else if (step.type === "observation") {
                                travelPlanContent += `### 단계 ${
                                    idx + 1
                                } - 👁️ 관찰\n\`\`\`\n${
                                    step.content
                                }\n\`\`\`\n\n`;
                            }
                        }
                    );

                    travelPlanContent += "</details>\n";
                }

                taskElement = (
                    <ProcessMessage
                        key={`task-${taskId}-${currentMessageId || "default"}`}
                        type="react_agent"
                        role={task.role}
                        content={travelPlanContent}
                        timestamp={
                            task.completed_at
                                ? new Date(task.completed_at * 1000)
                                : new Date()
                        }
                        taskDescription={`${
                            task.description || "여행 계획"
                        } (ReAct 패턴)`}
                        taskIndex={task.index}
                        status={task.status}
                        messageId={messageIdForProps}
                        stepInfo={{
                            total: stepsCount,
                            reasoning: reasoningSteps,
                            action: actionSteps,
                            observation: observationSteps,
                        }}
                    />
                );
            } else {
                // 일반 에이전트 결과
                taskElement = (
                    <ProcessMessage
                        key={`task-${taskId}-${currentMessageId || "default"}`}
                        type="agent_result"
                        role={task.role}
                        content={resultContent}
                        timestamp={
                            task.completed_at
                                ? new Date(task.completed_at * 1000)
                                : new Date()
                        }
                        taskDescription={
                            task.description || `${task.role} 태스크`
                        }
                        taskIndex={task.index}
                        status={task.status}
                        messageId={messageIdForProps}
                    />
                );
            }

            // 같은 role을 가진 결과가 이미 있는지 확인
            const existingRoleIndex =
                updatedUnit.systemResponses.taskResults.findIndex((element) => {
                    // React 요소의 props에 접근
                    const props = (element as any).props;
                    return props && props.role === task.role;
                });

            // 같은 role의 태스크가 있으면 업데이트, 없으면 추가
            if (existingRoleIndex >= 0) {
                // 기존에 있던 결과 제거하고 새 결과로 대체
                updatedUnit.systemResponses.taskResults[existingRoleIndex] =
                    taskElement;
                console.log(`[태스크 결과] 기존 역할(${task.role}) 업데이트`);
            } else {
                // 새 역할의 태스크 결과 추가
                updatedUnit.systemResponses.taskResults.push(taskElement);
                console.log(`[태스크 결과] 새 역할(${task.role}) 추가`);
            }

            return updatedUnit;
        });
    };

    // 태스크 분해 결과 업데이트 함수 - boolean 반환으로 수정
    const updateTaskDecomposition = (data: any): boolean => {
        // 데이터가 없는 경우
        if (!data) {
            console.error("[태스크 분리] 유효하지 않은 데이터:", data);
            return false;
        }

        // 메시지 ID가 현재와 다른 경우 처리하지 않음
        if (
            data.message_id &&
            currentMessageId &&
            data.message_id !== currentMessageId
        ) {
            console.log(
                `[태스크 분리] 다른 메시지의 태스크 분해입니다. 현재: ${currentMessageId}, 응답: ${data.message_id}. 무시합니다.`
            );
            return false;
        }

        console.log("[태스크 분리] 렌더링 시작:", data);

        try {
            setCurrentConversationUnit((prev) => {
                if (!prev) {
                    console.error("[태스크 분리] 현재 대화 단위가 없습니다");
                    return null;
                }

                // 업데이트할 유닛 복사
                const updatedUnit = { ...prev };

                // 태스크 분할 내용 렌더링 (원래 형식으로 변경)
                updatedUnit.systemResponses.taskDecomposition = (
                    <ProcessMessage
                        key={`task-decomposition-${
                            currentMessageId || conversationId || Date.now()
                        }`}
                        type="task_split"
                        role="task_manager"
                        content={formatTaskDecomposition(data)}
                        timestamp={new Date()}
                        taskDescription="태스크 분할"
                        messageId={data.message_id || currentMessageId}
                    />
                );

                return updatedUnit;
            });

            return true;
        } catch (error) {
            console.error("[태스크 분리] 렌더링 오류:", error);
            return false;
        }
    };

    // 태스크 분해 내용 포맷 함수 추가
    const formatTaskDecomposition = (data: any): string => {
        try {
            // tasks 배열이 있는 경우
            if (data.tasks && Array.isArray(data.tasks)) {
                // 원래 형식으로 돌아가기: 글머리 기호로 태스크 나열
                return data.tasks
                    .map(
                        (task: any) =>
                            `- ${task.description || task.role || "태스크"}`
                    )
                    .join("\n");
            }

            // tasks 배열이 없는 경우, message 필드가 있는지 확인
            if (data.message) {
                return data.message;
            }

            // 어느 것도 없으면 데이터 전체를 문자열로 변환
            if (typeof data === "object") {
                return JSON.stringify(data, null, 2);
            }

            // 그 외의 경우
            return String(data || "태스크 분할이 진행 중입니다...");
        } catch (error) {
            console.error("[태스크 분할] 포맷 오류:", error);
            return "태스크 분할 오류가 발생했습니다.";
        }
    };

    // 태스크 결과 처리 useEffect
    useEffect(() => {
        if (!agentTasksData) {
            console.log("[에이전트 결과] 데이터 없음");
            return;
        }

        console.log("[에이전트 결과] 데이터:", agentTasksData);
        console.log(
            "[에이전트 결과] JSON:",
            JSON.stringify(agentTasksData, null, 2)
        );

        // 응답에서 메시지 ID와 대화 ID 확인
        const responseMessageId = agentTasksData.message_id || "";
        const responseConversationId = agentTasksData.conversation_id || "";

        // 응답 메시지 ID가 현재 추적 중인 메시지 ID와 다른 경우 무시
        if (
            responseMessageId &&
            currentMessageId &&
            responseMessageId !== currentMessageId
        ) {
            console.log(
                `[에이전트 결과] 다른 메시지의 응답이 도착했습니다. 현재: ${currentMessageId}, 응답: ${responseMessageId}. 무시합니다.`
            );
            return;
        }

        // 응답 대화 ID가 현재 추적 중인 대화 ID와 다른 경우 무시
        if (
            responseConversationId &&
            conversationId &&
            responseConversationId !== conversationId
        ) {
            console.log(
                `[에이전트 결과] 다른 대화의 응답이 도착했습니다. 현재: ${conversationId}, 응답: ${responseConversationId}. 무시합니다.`
            );
            return;
        }

        // ReAct 에이전트 태스크 특별 처리 추가
        const hasReActTasks =
            agentTasksData.tasks &&
            agentTasksData.tasks.some(
                (task: any) =>
                    task.role === "travel_planner" &&
                    task.status === "completed"
            );

        // 모든 태스크 완료 여부 확인
        const allTasksCompleted =
            agentTasksData.tasks &&
            Array.isArray(agentTasksData.tasks) &&
            agentTasksData.tasks.length > 0 &&
            agentTasksData.tasks.every(
                (task: any) => task.status === "completed"
            );

        if (allTasksCompleted) {
            console.log("[에이전트 결과] 모든 태스크 완료 감지");

            // 태스크가 모두 완료된 경우 태스크 폴링 중지 및 최종 결과 폴링 시작
            setPollingState({
                decompositionPolling: false,
                taskResultPolling: false, // 태스크 폴링 중단
                finalResultPolling: true, // 최종 결과 폴링 시작
            });

            // React Query 폴링 명시적 중단 - 쿼리 비활성화
            queryClient.setQueryData(
                ["agentTasks", conversationId, currentMessageId],
                (oldData: any) => ({ ...oldData, _pollingDisabled: true })
            );
            queryClient.cancelQueries([
                "agentTasks",
                conversationId,
                currentMessageId,
            ]);

            console.log(
                "[시퀀스] 모든 태스크 완료되어 최종 결과 폴링으로 전환"
            );
        }

        if (hasReActTasks) {
            console.log("[ReAct 에이전트] 태스크 감지");
            // React 에이전트 태스크는 UI에 특별히 표시
            agentTasksData.tasks.forEach((task: any) => {
                if (task.role === "travel_planner") {
                    // steps_count 정보 확인
                    const stepsCount = task.result?.steps_count || 0;

                    // 메시지에 ReAct 패턴 정보 추가
                    if (
                        task.result &&
                        !task.result.react_info &&
                        stepsCount > 0
                    ) {
                        task.result.react_info = `이 태스크는 ReAct(추론-행동-관찰) 패턴으로 처리되었으며 총 ${stepsCount}회의 단계를 거쳤습니다.`;
                    }

                    // 태스크 결과 업데이트 (UI 반영)
                    updateTaskResult({
                        ...task,
                        description: `${
                            task.description || "여행 계획 생성"
                        } (ReAct 단계: ${stepsCount})`,
                    });
                } else {
                    // 다른 에이전트의 태스크는 일반적으로 처리
                    updateTaskResult(task);
                }
            });
        } else {
            // 일반 태스크 처리 (기존 코드)
            if (agentTasksData.tasks) {
                agentTasksData.tasks.forEach((task: any) => {
                    updateTaskResult(task);

                    // 태스크 ID 기록 (완료된 태스크 추적용)
                    if (task.status === "completed") {
                        setCompletedTaskIds(
                            (prev) => new Set([...prev, task.id])
                        );
                    }
                });
            }
        }

        // 예상된 에이전트 태스크 개수와 완료된 태스크 개수 비교
        if (
            expectedAgentTasks > 0 &&
            completedTaskIds.size >= expectedAgentTasks
        ) {
            console.log(
                `[에이전트 결과] 모든 태스크 완료: ${completedTaskIds.size}/${expectedAgentTasks}`
            );

            // 모든 태스크가 완료된 경우 최종 결과 폴링 시작
            setPollingState({
                decompositionPolling: false,
                taskResultPolling: false,
                finalResultPolling: true,
            });

            // React Query 폴링 명시적 중단 - 쿼리 비활성화
            queryClient.setQueryData(
                ["agentTasks", conversationId, currentMessageId],
                (oldData: any) => ({ ...oldData, _pollingDisabled: true })
            );
            queryClient.cancelQueries([
                "agentTasks",
                conversationId,
                currentMessageId,
            ]);

            console.log(
                "[시퀀스] 에이전트 태스크 모두 완료, 최종 결과 폴링 시작"
            );
        }
    }, [
        agentTasksData,
        currentMessageId,
        completedTaskIds,
        conversationId,
        queryClient,
        expectedAgentTasks,
    ]);

    // 최종 결과 처리 useEffect
    useEffect(() => {
        if (!finalResultData) {
            console.log("[최종 결과] 데이터 없음");
            return;
        }

        console.log("[최종 결과] 데이터:", finalResultData);
        console.log(
            "[최종 결과] JSON:",
            JSON.stringify(finalResultData, null, 2)
        );

        // 응답에서 메시지 ID와 대화 ID 확인
        const responseMessageId = finalResultData.message_id || "";
        const responseConversationId = finalResultData.conversation_id || "";

        // 응답 메시지 ID가 현재 추적 중인 메시지 ID와 다른 경우 무시
        if (
            responseMessageId &&
            currentMessageId &&
            responseMessageId !== currentMessageId
        ) {
            console.log(
                `[최종 결과] 다른 메시지의 응답이 도착했습니다. 현재: ${currentMessageId}, 응답: ${responseMessageId}. 무시합니다.`
            );
            return;
        }

        // 응답 대화 ID가 현재 추적 중인 대화 ID와 다른 경우 무시
        if (
            responseConversationId &&
            conversationId &&
            responseConversationId !== conversationId
        ) {
            console.log(
                `[최종 결과] 다른 대화의 응답이 도착했습니다. 현재: ${conversationId}, 응답: ${responseConversationId}. 무시합니다.`
            );
            return;
        }

        // 응답에서 메시지 ID 확인
        if (
            finalResultData.message_id &&
            (!currentMessageId ||
                currentMessageId !== finalResultData.message_id)
        ) {
            console.log(
                `[최종 결과] 응답에서 메시지 ID 업데이트: ${finalResultData.message_id}`
            );
            setCurrentMessageId(finalResultData.message_id);
        }

        // 에러 응답 처리
        if (finalResultData.error) {
            console.log(
                `[최종 결과] 에러 응답: ${finalResultData.error}, 폴링 계속`
            );
            return; // 폴링 계속
        }

        // 디버깅용 로그 추가
        console.log(
            `[최종 결과] 데이터 분석: message=${!!finalResultData.message}, result=${!!finalResultData.result}, status=${
                finalResultData.status
            }, _forceStopped=${
                (finalResultData as any)._forceStopped
            }, 전체 응답:`,
            JSON.stringify(finalResultData)
        );

        // 최종 결과가 있으면 즉시 폴링 중단 (message, result, 또는 status가 completed인 경우)
        if (
            finalResultData.message ||
            finalResultData.result ||
            finalResultData.status === "completed"
        ) {
            console.log(
                `[시퀀스] 최종 결과 수신 완료, 폴링 중단: ${
                    finalResultData.message
                        ? finalResultData.message.slice(0, 30)
                        : finalResultData.result
                        ? JSON.stringify(finalResultData.result).slice(0, 30)
                        : `상태: ${finalResultData.status}`
                }...`
            );

            // 최종 결과 폴링 명시적 강제 중단
            // 1. 상태 변경 - 모든 폴링 중지
            setPollingState({
                decompositionPolling: false,
                taskResultPolling: false,
                finalResultPolling: false, // 최종 결과 폴링 중단
            });

            // 2. React Query 쿼리 캐시 강제 수정 및 쿼리 취소 - 즉시 실행
            window.setTimeout(() => {
                // 폴링 중단 플래그 추가
                queryClient.setQueryData(
                    ["finalResult", conversationId, currentMessageId],
                    (oldData: any) => ({
                        ...(oldData || {}),
                        _pollingDisabled: true,
                        _forceStopped: true,
                    })
                );

                // 쿼리 취소 - 정확한 쿼리만
                queryClient.cancelQueries(
                    ["finalResult", conversationId, currentMessageId],
                    { exact: true }
                );

                console.log("[시퀀스] 최종 결과 폴링 강제 중단 완료");

                // 상태 재확인
                const updatedData = queryClient.getQueryData([
                    "finalResult",
                    conversationId,
                    currentMessageId,
                ]);
                console.log("[시퀀스] 중단 후 쿼리 상태:", updatedData);
            }, 0);

            // 메시지 데이터 추가
            const messageContent =
                finalResultData.message ||
                (finalResultData.result &&
                    extractMessage(finalResultData.result));

            // 메시지 내용이 있거나 status가 completed인 경우
            if (messageContent || finalResultData.status === "completed") {
                // 최종 응답이 완료되었음을 표시하고 자동 스크롤 비활성화
                setResponseCompleted(true);

                // 마지막 스크롤을 위해 약간의 지연 후 자동 스크롤 비활성화
                setTimeout(() => {
                    setAutoScrollEnabled(false);
                    console.log("[스크롤] 자동 스크롤 비활성화됨");
                }, 1000);

                // 봇 응답 메시지 생성 - status는 있지만 message 내용이 없는 경우 처리
                const content = messageContent || "처리가 완료되었습니다.";

                const botMessage: Message = {
                    role: "assistant",
                    content: content,
                    timestamp: new Date(),
                    conversationId: conversationId || undefined,
                    finalResult: true,
                    id: finalResultData.message_id || undefined, // 메시지 ID 추가
                };

                // 대화에 봇 메시지 추가
                setMessages((prevMessages) => [...prevMessages, botMessage]);

                // 현재 대화 단위에 최종 응답 추가
                setCurrentConversationUnit((prev) => {
                    if (!prev) return null;

                    return {
                        ...prev,
                        systemResponses: {
                            ...prev.systemResponses,
                            finalResponse: botMessage,
                        },
                    };
                });

                // 폴링 및 로딩 상태 초기화
                setPollingState({
                    decompositionPolling: false,
                    taskResultPolling: false,
                    finalResultPolling: false,
                });
                setWaitingForResponse(false);

                // 실행 완료 콜백 호출 (있는 경우)
                if (onTaskCreated) {
                    console.log("[시퀀스] 태스크 생성 완료 콜백 호출");
                    onTaskCreated(conversationId as string);
                }
            }
        } else {
            console.log("[최종 결과] 메시지 없음, 폴링 계속");
        }
    }, [
        finalResultData,
        currentMessageId,
        conversationId,
        queryClient,
        onTaskCreated,
    ]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim() || queryMutation.isLoading || waitingForResponse)
            return;

        // 새 요청 시 자동 스크롤과 응답 완료 상태 초기화
        setAutoScrollEnabled(true);
        setResponseCompleted(false);

        // 이전 처리 상태 완전히 초기화
        resetProcessingState();

        // 이전 대화가 있으면 완료된 대화로 이동
        if (currentConversationUnit) {
            setCompletedUnits((prev) => [...prev, currentConversationUnit]);
        }

        // 대화 ID가 없으면 생성, 있으면 유지 (새로운 메시지만 생성)
        const currentConvId = conversationId || generateConversationId();
        if (!conversationId) {
            setConversationId(currentConvId);
            console.log(`[요청] 새 대화 ID 생성: ${currentConvId}`);
        } else {
            console.log(`[요청] 기존 대화 ID 사용: ${currentConvId}`);
        }

        // 메시지 ID를 클라이언트에서 생성
        const newMessageId = generateMessageId();
        setCurrentMessageId(newMessageId);
        console.log(`[요청] 클라이언트에서 생성한 메시지 ID: ${newMessageId}`);

        // 새 사용자 메시지 생성
        const userMessage: Message = {
            role: "user",
            content: query,
            timestamp: new Date(),
            conversationId: currentConvId,
            id: newMessageId, // 메시지 ID 추가
        };

        // 새 사용자 메시지 저장
        setMessages((prev) => [...prev, userMessage]);

        // 새 대화 단위 생성 (사용자 메시지가 바로 표시됨)
        setCurrentConversationUnit({
            userMessage,
            systemResponses: {
                taskResults: [],
            },
        });

        const request: QueryRequest = {
            query: query.trim(),
            conversation_id: currentConvId,
            message_id: newMessageId, // 메시지 ID 요청에 포함
        };

        // 요청 정보 로깅
        console.log(
            "[요청] API 요청 데이터:",
            JSON.stringify(request, null, 2)
        );

        // 쿼리 요청 즉시 처리 중 상태로 설정
        setWaitingForResponse(true);

        // 메시지 ID가 이미 있으므로 바로 태스크 분해 폴링 시작
        console.log(
            `[시퀀스] 쿼리 요청 시작, 메시지 ID=${newMessageId} 바로 사용`
        );
        setPollingState({
            decompositionPolling: true, // 요청과 동시에 바로 폴링 시작
            taskResultPolling: false,
            finalResultPolling: false,
        });

        queryMutation.mutate(request);

        setQuery("");
        eventEmitter.emit("querySubmitted", {});
    };

    // 컴포넌트 언마운트 시 정리
    useEffect(() => {
        return () => {
            // 정리 로직
        };
    }, []);

    // 이 기존 useEffect를 완전히 제거합니다
    /*useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [completedUnits, currentConversationUnit, messages]);*/

    // 사용자 메시지 렌더링 함수
    const renderUserMessage = (message: Message, key: string) => (
        <div key={key} className="flex justify-end">
            <div className="max-w-lg px-4 py-2 rounded-lg shadow-md bg-blue-500 text-white">
                <ReactMarkdown>{message.content}</ReactMarkdown>
                <div className="text-xs mt-1 text-blue-100 text-right">
                    {message.timestamp.toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                    })}
                </div>
            </div>
        </div>
    );

    // 최종 응답 메시지 렌더링 함수
    const renderFinalResponse = (message: Message, key: string) => (
        <div key={key} className="flex justify-start">
            <div className="max-w-lg px-4 py-2 rounded-lg shadow-md bg-white text-gray-800 border border-gray-200">
                <ReactMarkdown>{message.content}</ReactMarkdown>
                <div className="text-xs mt-1 text-gray-400 text-left">
                    {message.timestamp.toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                    })}
                </div>
            </div>
        </div>
    );

    // 현재 대화 단위 렌더링 함수
    const renderCurrentConversation = () => {
        if (!currentConversationUnit) return null;

        return (
            <div className="space-y-4">
                {/* 사용자 메시지 */}
                {renderUserMessage(
                    currentConversationUnit.userMessage,
                    `current-user`
                )}

                {/* 진행 중인 시스템 응답들 */}
                <div className="pl-6 space-y-2">
                    {/* 태스크 분해 중 로딩 표시 */}
                    {pollingState.decompositionPolling &&
                        !currentConversationUnit.systemResponses
                            .taskDecomposition && (
                            <LoadingMessage type="decomposition" />
                        )}

                    {/* 태스크 분할 결과 */}
                    {currentConversationUnit.systemResponses.taskDecomposition}

                    {/* 에이전트 작업 중 로딩 표시 */}
                    {pollingState.taskResultPolling && (
                        <LoadingMessage type="agent" />
                    )}

                    {/* 태스크 결과들 */}
                    {currentConversationUnit.systemResponses.taskResults.map(
                        (taskResult, taskIndex) =>
                            React.cloneElement(taskResult, {
                                key: `current-task-${taskIndex}`,
                            })
                    )}

                    {/* 결과 통합 중 로딩 표시 */}
                    {pollingState.finalResultPolling &&
                        !currentConversationUnit.systemResponses
                            .finalResponse && (
                            <LoadingMessage type="integration" />
                        )}

                    {/* 최종 응답 */}
                    {currentConversationUnit.systemResponses.finalResponse &&
                        renderFinalResponse(
                            currentConversationUnit.systemResponses
                                .finalResponse,
                            `current-final`
                        )}
                </div>
            </div>
        );
    };

    // 대화 목록 토글 함수
    const toggleConversationList = () => {
        setShowConversationList(!showConversationList);
        if (!showConversationList) {
            refetchConversations(); // 목록 열 때 최신 데이터 조회
        }
    };

    // 시간 포맷팅 함수
    const formatTime = (timestamp: number) => {
        if (!timestamp) return "-";
        return new Date(timestamp * 1000).toLocaleString();
    };

    // 스크롤 관련 useEffect 수정
    useEffect(() => {
        // 자동 스크롤이 활성화되어 있을 때만 스크롤 위치 조정
        if (scrollRef.current && autoScrollEnabled) {
            console.log("[스크롤] 자동 스크롤 실행");
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [completedUnits, currentConversationUnit, messages, autoScrollEnabled]);

    // 사용자 스크롤 감지 이벤트 추가
    useEffect(() => {
        const handleUserScroll = () => {
            // 응답이 완료된 상태에서 사용자가 스크롤을 움직이면 자동 스크롤 비활성화
            if (responseCompleted && scrollRef.current) {
                setAutoScrollEnabled(false);
                console.log(
                    "[스크롤] 사용자 스크롤 감지, 자동 스크롤 비활성화"
                );
            }
        };

        // 스크롤 이벤트 리스너 등록
        const scrollElement = scrollRef.current;
        if (scrollElement) {
            scrollElement.addEventListener("scroll", handleUserScroll);
        }

        // 컴포넌트 언마운트 시 이벤트 리스너 제거
        return () => {
            if (scrollElement) {
                scrollElement.removeEventListener("scroll", handleUserScroll);
            }
        };
    }, [responseCompleted]);

    return (
        <div className="flex flex-col h-full bg-gray-50 p-4">
            {/* 대화 목록 토글 버튼 */}
            <div className="mb-4 flex justify-between items-center">
                <button
                    onClick={toggleConversationList}
                    className="px-3 py-1.5 bg-blue-500 text-white rounded-md hover:bg-blue-600 text-sm flex items-center"
                >
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-4 w-4 mr-1"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                    >
                        <path
                            fillRule="evenodd"
                            d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z"
                            clipRule="evenodd"
                        />
                    </svg>
                    {showConversationList ? "대화 목록 닫기" : "대화 목록 보기"}
                </button>

                {conversationId && (
                    <div className="text-xs text-gray-500">
                        현재 대화 ID: {conversationId}
                    </div>
                )}
            </div>

            {/* 대화 목록 */}
            {showConversationList && (
                <div className="mb-4 border rounded-lg bg-white shadow-sm">
                    <div className="bg-blue-50 px-4 py-2 flex justify-between items-center border-b">
                        <h3 className="font-medium text-blue-700">
                            최근 대화 목록
                        </h3>
                        <button
                            onClick={() => refetchConversations()}
                            className="text-xs text-blue-600 hover:text-blue-800"
                        >
                            새로고침
                        </button>
                    </div>
                    <div className="max-h-60 overflow-y-auto">
                        {isConversationsLoading ? (
                            <div className="p-4 text-center text-gray-500">
                                로딩 중...
                            </div>
                        ) : !conversations || conversations.length === 0 ? (
                            <div className="p-4 text-center text-gray-500">
                                대화 내역이 없습니다
                            </div>
                        ) : (
                            <div className="divide-y">
                                {conversations.map((conv: any) => (
                                    <div
                                        key={conv.conversation_id}
                                        className={`px-4 py-2 hover:bg-gray-50 cursor-pointer ${
                                            conversationId ===
                                            conv.conversation_id
                                                ? "bg-blue-50"
                                                : ""
                                        }`}
                                        onClick={() =>
                                            loadConversationMessages(
                                                conv.conversation_id
                                            )
                                        }
                                    >
                                        <div className="font-medium text-sm truncate">
                                            {conv.query || "제목 없음"}
                                        </div>
                                        <div className="flex justify-between text-xs text-gray-500 mt-1">
                                            <div className="flex items-center">
                                                <span
                                                    className={`inline-block w-2 h-2 rounded-full mr-1 ${
                                                        conv.status ===
                                                        "completed"
                                                            ? "bg-green-500"
                                                            : "bg-blue-500"
                                                    }`}
                                                ></span>
                                                <span>
                                                    {conv.task_count}개 태스크
                                                </span>
                                            </div>
                                            <span>
                                                {formatTime(conv.created_at)}
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                    <div className="border-t px-4 py-2">
                        <button
                            onClick={() => {
                                setConversationId(null);
                                setCompletedUnits([]);
                                setCurrentConversationUnit(null);
                                setShowConversationList(false);
                            }}
                            className="w-full text-center text-sm text-blue-600 hover:text-blue-800"
                        >
                            새 대화 시작
                        </button>
                    </div>
                </div>
            )}

            <div
                ref={scrollRef}
                className="flex-grow overflow-y-auto space-y-4 mb-4 pr-2"
            >
                {/* 완료된 대화 단위 렌더링 */}
                {completedUnits.map((unit, index) => (
                    <div key={`unit-${index}`} className="space-y-4">
                        {/* 사용자 메시지 */}
                        {renderUserMessage(unit.userMessage, `user-${index}`)}

                        {/* 시스템 응답들 */}
                        <div className="pl-6 space-y-2">
                            {/* 태스크 분할 결과 */}
                            {unit.systemResponses.taskDecomposition}

                            {/* 태스크 결과들 */}
                            {unit.systemResponses.taskResults.map(
                                (taskResult, taskIndex) =>
                                    React.cloneElement(taskResult, {
                                        key: `task-result-${index}-${taskIndex}`,
                                    })
                            )}

                            {/* 최종 응답 */}
                            {unit.systemResponses.finalResponse &&
                                renderFinalResponse(
                                    unit.systemResponses.finalResponse,
                                    `final-${index}`
                                )}
                        </div>
                    </div>
                ))}

                {/* 현재 진행 중인 대화 단위 */}
                {renderCurrentConversation()}
            </div>

            <form onSubmit={handleSubmit} className="mt-auto">
                <div className="flex space-x-2">
                    <input
                        type="text"
                        className="flex-grow rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-200 p-2"
                        placeholder="메시지를 입력하세요..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        disabled={waitingForResponse || queryMutation.isLoading}
                    />
                    <button
                        type="submit"
                        className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={
                            queryMutation.isLoading ||
                            waitingForResponse ||
                            !query.trim()
                        }
                    >
                        {queryMutation.isLoading || waitingForResponse ? (
                            <span>처리 중...</span>
                        ) : (
                            <span>전송</span>
                        )}
                    </button>
                </div>
            </form>

            {/* 에러 메시지 표시 */}
            {queryMutation.isError && (
                <div className="mt-4 text-red-600 text-sm">
                    요청 처리 중 오류가 발생했습니다:{" "}
                    {queryMutation.error instanceof Error
                        ? queryMutation.error.message
                        : "알 수 없는 오류"}
                </div>
            )}
        </div>
    );
};

export default RequestForm;
