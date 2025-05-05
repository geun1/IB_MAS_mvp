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

    console.log("응답 데이터 분석:", data); // 디버깅용 로깅

    // 결과가 이미 문자열인 경우
    if (typeof data === "string") {
        console.log("결과가 직접 문자열");
        return data;
    }

    // 직접 'message' 필드가 있고 내용이 있는 경우
    if (
        data.message &&
        data.message.trim() !== "처리가 완료되었으나 결과가 없습니다."
    ) {
        console.log("최상위 message 필드 감지");
        return String(data.message);
    }

    // tasks 배열이 있는 경우
    if (data.tasks && Array.isArray(data.tasks) && data.tasks.length > 0) {
        console.log("tasks 배열 감지");

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
                    console.log("task.result.result.content 구조 감지");
                    return String(lastTask.result.result.content);
                }

                // 구조: result > message
                if (lastTask.result.message) {
                    console.log("task.result.message 구조 감지");
                    return String(lastTask.result.message);
                }

                // 구조: result > content
                if (lastTask.result.content) {
                    console.log("task.result.content 구조 감지");
                    return String(lastTask.result.content);
                }

                // 구조: result > result > message
                if (lastTask.result.result && lastTask.result.result.message) {
                    console.log("task.result.result.message 구조 감지");
                    return String(lastTask.result.result.message);
                }

                // 구조: result가 직접 문자열인 경우
                if (typeof lastTask.result === "string") {
                    console.log("task.result가 직접 문자열");
                    return lastTask.result;
                }

                // 구조: result가 객체이지만 다른 형태인 경우 JSON으로 반환
                if (typeof lastTask.result === "object") {
                    try {
                        console.log("task.result가 객체, JSON으로 변환");
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
        console.log("result.result 구조 감지");
        if (data.result.result.content) {
            console.log("result.result.content 감지");
            return String(data.result.result.content);
        }
        if (data.result.result.message) {
            console.log("result.result.message 감지");
            return String(data.result.result.message);
        }
        return "";
    }

    // 단일 수준 구조인 경우 (result.message/content)
    if (data.result && typeof data.result === "object") {
        console.log("result 객체 구조 감지");
        if (data.result.content) {
            console.log("result.content 감지");
            return String(data.result.content);
        }
        if (data.result.message) {
            console.log("result.message 감지");
            return String(data.result.message);
        }

        // 결과가 있지만 예상 구조가 아닌 경우 JSON으로 변환
        try {
            console.log("result가 비표준 구조, JSON으로 변환");
            return JSON.stringify(data.result, null, 2);
        } catch (e) {
            console.error("JSON 변환 오류:", e);
        }
    }

    // 아무것도 찾지 못했지만 데이터가 있는 경우
    if (data) {
        try {
            console.log("비표준 데이터 구조, 전체를 JSON으로 변환");
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

const RequestForm: React.FC<RequestFormProps> = ({ onTaskCreated }) => {
    const [query, setQuery] = useState("");
    const [userMessages, setUserMessages] = useState<Message[]>([]); // 사용자 메시지만 저장
    const [currentConversationUnit, setCurrentConversationUnit] =
        useState<ConversationUnit | null>(null); // 현재 진행 중인 대화 단위
    const [completedUnits, setCompletedUnits] = useState<ConversationUnit[]>(
        []
    ); // 완료된 대화 단위들
    const [conversationId, setConversationId] = useState<string | null>(null);
    const [waitingForResponse, setWaitingForResponse] = useState(false);

    // 각 단계별 폴링 상태
    const [pollingState, setPollingState] = useState<PollingState>({
        decompositionPolling: false,
        taskResultPolling: false,
        finalResultPolling: false,
    });

    // 태스크 분리 결과 저장
    const [taskDecomposition, setTaskDecomposition] = useState<{
        conversation_id?: string;
        tasks: TaskDecompositionItem[];
    } | null>(null);
    // 태스크 ID 목록
    const [taskIds, setTaskIds] = useState<string[]>([]);
    // 완료된 태스크 ID 목록
    const [completedTaskIds, setCompletedTaskIds] = useState<Set<string>>(
        new Set()
    );

    const queryClient = useQueryClient();
    const scrollRef = useRef<HTMLDivElement>(null);

    // useMutation 정의 (타입 명시)
    const queryMutation = useMutation<QueryResponse, Error, QueryRequest>(
        (request: QueryRequest) => orchestratorApi.processQuery(request),
        {
            onSuccess: (data) => {
                console.log("쿼리 요청 성공:", data);
                if (data.conversation_id) {
                    setConversationId(data.conversation_id);
                } else {
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

    // 태스크 분리 결과 폴링 쿼리
    const { data: decompositionData, refetch: refetchDecomposition } = useQuery(
        ["taskDecomposition", conversationId],
        async () => {
            if (!conversationId) throw new Error("대화 ID가 없습니다");

            console.log(`[태스크 분리] 폴링 시도: ${conversationId}`);

            // 분리된 태스크 분리 API 호출
            const response = await orchestratorApi.getTaskDecomposition(
                conversationId
            );

            console.log("[태스크 분리] 응답:", response);
            return response;
        },
        {
            // conversationId가 있고 decompositionPolling이 true일 때만 활성화
            enabled: !!conversationId && pollingState.decompositionPolling,
            refetchInterval: 1000, // 1초마다 폴링
            // 성공한 경우에도 refetch 계속 수행
            refetchOnWindowFocus: false,
            retry: true,
            retryDelay: 1000,
            onSuccess: (data) => {
                if (!data || !data.tasks || data.tasks.length === 0) {
                    console.log("[태스크 분리] 결과 없음, 폴링 계속...");
                    return;
                }

                console.log("[태스크 분리] 성공:", data);

                // 태스크 분리 결과 저장
                setTaskDecomposition(data);

                // 태스크 ID 목록 추출 - index를 ID로 사용
                const ids = data.tasks.map(
                    (task: TaskDecompositionItem, index: number) =>
                        task.index?.toString() || index.toString()
                );
                console.log("[태스크 분리] 태스크 ID 목록:", ids);
                setTaskIds(ids);

                // 태스크 분리 결과 즉시 렌더링
                updateTaskDecomposition(data);

                // *** 중요: 태스크 분리 폴링 즉시 중단하고 태스크 결과 폴링 시작 ***
                console.log(
                    "[시퀀스] 태스크 분리 완료, 에이전트 태스크 결과 폴링 시작"
                );
                setPollingState({
                    decompositionPolling: false, // 태스크 분리 폴링 중단
                    taskResultPolling: true, // 태스크 결과 폴링 시작
                    finalResultPolling: false,
                });
            },
            onError: (error) => {
                console.error("[태스크 분리] 조회 오류:", error);
            },
        }
    );

    // 에이전트 태스크 결과 폴링 쿼리
    const { data: taskResultsData, refetch: refetchTaskResults } = useQuery(
        ["taskResults", conversationId],
        async () => {
            if (!conversationId) throw new Error("대화 ID가 없습니다");

            console.log(`[에이전트 결과] 폴링 시도: ${conversationId}`);

            // 분리된 태스크 결과 API 호출
            const response = await orchestratorApi.getAgentTasks(
                conversationId
            );

            console.log("[에이전트 결과] 응답:", response);
            return response;
        },
        {
            // conversationId가 있고 taskResultPolling이 true일 때만 활성화
            enabled: !!conversationId && pollingState.taskResultPolling,
            refetchInterval: 1000, // 1초마다 폴링
            refetchOnWindowFocus: false,
            retry: true,
            retryDelay: 1000,
            onSuccess: (data) => {
                if (!data || !data.tasks || data.tasks.length === 0) {
                    console.log("[에이전트 결과] 결과 없음, 폴링 계속...");
                    return;
                }

                console.log("[에이전트 결과] 데이터:", data);
                console.log(
                    "[에이전트 결과] 현재 완료된 태스크:",
                    Array.from(completedTaskIds)
                );

                // 완료된 태스크 추적
                const newCompletedTasks = new Set(completedTaskIds);
                let hasNewCompletedTask = false;

                // 모든 태스크를 화면에 표시하고 완료된 태스크 추적
                data.tasks.forEach((task: TaskItem) => {
                    // 태스크 ID 확인 - id가 없는 경우 index를 사용
                    const taskId = task.id || task.index?.toString() || "";
                    console.log(
                        `[에이전트 결과] 태스크 확인: ID=${taskId}, 상태=${task.status}, 역할=${task.role}`
                    );

                    // 완료된 태스크이고 아직 처리되지 않은 경우
                    if (
                        task.status === "completed" &&
                        taskId &&
                        !completedTaskIds.has(taskId)
                    ) {
                        console.log(
                            `[에이전트 결과] 새 완료 태스크 발견: ${taskId}`
                        );
                        newCompletedTasks.add(taskId);
                        hasNewCompletedTask = true;
                    }

                    // 상태와 관계없이 모든 태스크 결과 표시 (업데이트)
                    updateTaskResult(task);
                });

                // 새로 완료된 태스크가 있으면 상태 업데이트
                if (hasNewCompletedTask) {
                    console.log(
                        "[에이전트 결과] 완료된 태스크 업데이트:",
                        Array.from(newCompletedTasks)
                    );
                    setCompletedTaskIds(newCompletedTasks);
                }

                // 모든 태스크가 완료되었는지 확인 (두 가지 조건 확인)
                const allTasksCompleted =
                    // 1. taskIds 유효성 확인
                    taskIds.length > 0 &&
                    // 2. 완료된 태스크 개수가 전체 태스크 개수와 같거나 큰 경우
                    (newCompletedTasks.size >= taskIds.length ||
                        // 3. 서버에서 받은 태스크 개수가 전체 태스크 개수와 같거나 크고, 모두 완료 상태인 경우
                        (data.tasks.length >= taskIds.length &&
                            data.tasks.every(
                                (task: TaskItem) => task.status === "completed"
                            )));

                console.log(
                    `[에이전트 결과] 태스크 진행 상황: ${
                        Array.from(newCompletedTasks).length
                    }/${
                        taskIds.length
                    } 완료, 모두 완료됨: ${allTasksCompleted}, 서버 태스크 개수: ${
                        data.tasks.length
                    }`
                );

                // 모든 태스크가 완료되면 태스크 결과 폴링 중단하고 최종 결과 폴링 시작
                if (allTasksCompleted) {
                    console.log(
                        "[시퀀스] 모든 태스크 완료, 최종 결과 폴링 시작"
                    );
                    setPollingState({
                        decompositionPolling: false,
                        taskResultPolling: false, // 태스크 결과 폴링 중단
                        finalResultPolling: true, // 최종 결과 폴링 시작
                    });
                }
            },
            onError: (error) => {
                console.error("[에이전트 결과] 조회 오류:", error);
            },
        }
    );

    // 최종 통합 결과 폴링 쿼리
    const { data: finalResultData, refetch: refetchFinalResult } = useQuery(
        ["finalResult", conversationId],
        async () => {
            if (!conversationId) throw new Error("대화 ID가 없습니다");

            console.log(`[최종 결과] 폴링 시도: ${conversationId}`);

            // 분리된 최종 결과 API 호출
            const response = await orchestratorApi.getFinalResult(
                conversationId
            );

            console.log("[최종 결과] 응답:", response);
            return response;
        },
        {
            // conversationId가 있고 finalResultPolling이 true일 때만 활성화
            enabled: !!conversationId && pollingState.finalResultPolling,
            refetchInterval: 1000, // 1초마다 폴링
            refetchOnWindowFocus: false,
            retry: true,
            retryDelay: 1000,
            onSuccess: (data) => {
                if (!data || !data.message) {
                    console.log("[최종 결과] 메시지 없음, 폴링 계속...");
                    return;
                }

                console.log("[최종 결과] 성공:", data);

                // 최종 결과가 있으면 즉시 렌더링하고 모든 폴링 중단
                if (data.message) {
                    // 최종 결과 즉시 렌더링
                    updateFinalResult(data);

                    // 모든 폴링 중단
                    console.log("[시퀀스] 최종 결과 완료, 모든 폴링 종료");
                    setPollingState({
                        decompositionPolling: false,
                        taskResultPolling: false,
                        finalResultPolling: false, // 최종 결과 폴링 중단
                    });

                    // 응답 대기 상태 해제
                    setWaitingForResponse(false);

                    // 현재 대화 단위를 완료된 대화 단위로 이동
                    setCurrentConversationUnit((prev) => {
                        if (prev) {
                            setCompletedUnits((units) => [...units, prev]);
                            return null;
                        }
                        return prev;
                    });
                }
            },
            onError: (error) => {
                console.error("[최종 결과] 조회 오류:", error);
            },
        }
    );

    // useEffect를 사용하여 폴링 상태 변경 시 적절한 refetch 트리거
    useEffect(() => {
        // conversationId가 없으면 아무 작업도 수행하지 않음
        if (!conversationId) return;

        if (pollingState.decompositionPolling && refetchDecomposition) {
            // 태스크 분리 결과 폴링 시작
            refetchDecomposition();
        } else if (pollingState.taskResultPolling && refetchTaskResults) {
            // 에이전트 태스크 결과 폴링 시작
            refetchTaskResults();
        } else if (pollingState.finalResultPolling && refetchFinalResult) {
            // 최종 결과 폴링 시작
            refetchFinalResult();
        }
    }, [
        conversationId,
        pollingState.decompositionPolling,
        pollingState.taskResultPolling,
        pollingState.finalResultPolling,
        refetchDecomposition,
        refetchTaskResults,
        refetchFinalResult,
    ]);

    // 태스크 분리 결과 업데이트 함수
    const updateTaskDecomposition = (data: {
        tasks: TaskDecompositionItem[];
    }) => {
        if (!data || !data.tasks || data.tasks.length === 0) return;

        setCurrentConversationUnit((prev) => {
            const updatedUnit = prev || {
                userMessage: userMessages[userMessages.length - 1],
                systemResponses: {
                    taskResults: [],
                },
            };

            // 태스크 분할 내용 렌더링
            updatedUnit.systemResponses.taskDecomposition =
                renderTaskDecomposition(data);

            return updatedUnit;
        });
    };

    // 개별 태스크 결과 업데이트 함수
    const updateTaskResult = (task: TaskItem) => {
        if (!task) return;

        // 태스크에 role이 없는 경우 처리하지 않음
        if (!task.role) return;

        // taskId를 id 또는 index 값에서 가져옴
        const taskId =
            task.id ||
            task.index?.toString() ||
            Math.random().toString(36).substring(7);

        setCurrentConversationUnit((prev) => {
            if (!prev) return null;

            const updatedUnit = { ...prev };

            // 태스크 결과 요소 생성
            const taskElement = (
                <ProcessMessage
                    key={`ta***REMOVED***${taskId}`}
                    type="agent_result"
                    role={task.role}
                    content={
                        typeof task.result === "object"
                            ? JSON.stringify(task.result, null, 2)
                            : String(task.result || "결과 없음")
                    }
                    timestamp={
                        task.completed_at
                            ? new Date(task.completed_at * 1000)
                            : new Date()
                    }
                    taskDescription={task.description}
                    taskIndex={task.index}
                    status={task.status}
                />
            );

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
            } else {
                // 새 역할의 태스크 결과 추가
                updatedUnit.systemResponses.taskResults.push(taskElement);
            }

            return updatedUnit;
        });
    };

    // 최종 결과 업데이트 함수
    const updateFinalResult = (data: any) => {
        if (!data || !data.message) return;

        setCurrentConversationUnit((prev) => {
            if (!prev) return null;

            const updatedUnit = { ...prev };

            // 최종 응답 설정
            updatedUnit.systemResponses.finalResponse = {
                role: "assistant",
                content: data.message,
                timestamp: new Date(),
                conversationId: data.conversation_id,
                finalResult: true,
            };

            return updatedUnit;
        });
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim() || queryMutation.isLoading || waitingForResponse)
            return;

        const currentConvId = conversationId || generateConversationId();
        if (!conversationId) {
            setConversationId(currentConvId);
        }

        // 새 사용자 메시지 생성
        const userMessage: Message = {
            role: "user",
            content: query,
            timestamp: new Date(),
            conversationId: currentConvId,
        };

        // 이전 대화가 있으면 완료된 대화로 이동
        if (currentConversationUnit) {
            setCompletedUnits((prev) => [...prev, currentConversationUnit]);
            setCurrentConversationUnit(null);
        }

        // 새 사용자 메시지 저장
        setUserMessages((prev) => [...prev, userMessage]);

        const request: QueryRequest = {
            query: query.trim(),
            conversation_id: currentConvId,
        };

        // 쿼리 요청 즉시 처리 중 상태로 설정
        setWaitingForResponse(true);

        // 즉시 태스크 분리 폴링 시작 - 다른 폴링은 비활성화
        console.log("[시퀀스] 태스크 분리 폴링 시작");
        setPollingState({
            decompositionPolling: true,
            taskResultPolling: false,
            finalResultPolling: false,
        });

        // 완료된 태스크 초기화
        setCompletedTaskIds(new Set());
        setTaskIds([]);

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

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [completedUnits, currentConversationUnit, userMessages]);

    // taskDecomposition 렌더링 로직 분리
    const renderTaskDecomposition = (
        decomposition: {
            tasks: TaskDecompositionItem[];
        } | null
    ): JSX.Element | undefined => {
        if (
            !decomposition ||
            !decomposition.tasks ||
            decomposition.tasks.length === 0
        ) {
            return undefined;
        }

        // 태스크 분할 내용을 마크다운 포맷으로 변환
        const content = decomposition.tasks
            .map((task) => `- ${task.description} (${task.role})`)
            .join("\n");

        console.log("태스크 분할 렌더링:", content);

        return (
            <ProcessMessage
                key={`ta***REMOVED***decomposition-${conversationId}`}
                type="task_split"
                role="task_manager"
                content={content}
                timestamp={new Date()}
                taskDescription="태스크 분할"
            />
        );
    };

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

    return (
        <div className="flex flex-col h-full bg-gray-50 p-4">
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
                                        key: `ta***REMOVED***result-${index}-${taskIndex}`,
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
                {currentConversationUnit && (
                    <div className="space-y-4">
                        {/* 사용자 메시지 */}
                        {renderUserMessage(
                            currentConversationUnit.userMessage,
                            `current-user`
                        )}

                        {/* 현재 처리 중인 시스템 응답들 */}
                        <div className="pl-6 space-y-2">
                            {/* 태스크 분할 결과 */}
                            {
                                currentConversationUnit.systemResponses
                                    .taskDecomposition
                            }

                            {/* 태스크 결과들 */}
                            {currentConversationUnit.systemResponses.taskResults.map(
                                (taskResult, taskIndex) =>
                                    React.cloneElement(taskResult, {
                                        key: `current-ta***REMOVED***${taskIndex}`,
                                    })
                            )}

                            {/* 최종 응답 */}
                            {currentConversationUnit.systemResponses
                                .finalResponse &&
                                renderFinalResponse(
                                    currentConversationUnit.systemResponses
                                        .finalResponse,
                                    `current-final`
                                )}
                        </div>
                    </div>
                )}
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
