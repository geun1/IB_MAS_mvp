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
    const [messages, setMessages] = useState<Message[]>([]);
    const [conversationId, setConversationId] = useState<string | null>(null);
    const [waitingForResponse, setWaitingForResponse] = useState(false);
    const [conversationStatus, setConversationStatus] =
        useState<ConversationStatus | null>(null);

    const queryClient = useQueryClient();
    const scrollRef = useRef<HTMLDivElement>(null);
    const additionalPollsCount = useRef(0);
    const maxAdditionalPolls = 1;

    // useMutation 정의 (타입 명시)
    const queryMutation = useMutation<QueryResponse, Error, QueryRequest>(
        (request: QueryRequest) => orchestratorApi.processQuery(request),
        {
            onSuccess: (data) => {
                console.log("쿼리 요청 성공:", data);
                if (data.conversation_id) {
                    setConversationId(data.conversation_id);
                    setWaitingForResponse(true);
                    additionalPollsCount.current = 0;
                } else {
                    setWaitingForResponse(false);
                }
            },
            onError: (error) => {
                console.error("쿼리 요청 실패:", error);
                setWaitingForResponse(false);
            },
        }
    );

    // 대화 상태 폴링 로직 (타입 명시 및 인수 구조 확인)
    const {
        data: conversationData,
        refetch: refetchConversation,
        remove: removeConversationQuery,
    } = useQuery<ConversationStatus | null, Error>(
        // 인수 1: 쿼리 키
        ["conversationStatus", conversationId],
        // 인수 2: 쿼리 함수
        async () => {
            if (!conversationId) return null;
            try {
                const response = await orchestratorApi.getConversation(
                    conversationId
                );
                return response;
            } catch (error) {
                console.error("대화 상태 조회 오류:", error);
                return null;
            }
        },
        // 인수 3: 옵션 객체
        {
            enabled: waitingForResponse && !!conversationId,
            refetchInterval: 3000,
            staleTime: 2000,
            onSuccess: (data) => {
                if (!data) return;

                setConversationStatus(data);
                console.log("대화 상태 업데이트:", data);

                // 최종 사용자 메시지 추가
                if (
                    (data.status === "completed" ||
                        data.status === "partially_completed") &&
                    data.message
                ) {
                    const assistantMessage: Message = {
                        role: "assistant",
                        content: data.message,
                        timestamp: new Date(),
                        conversationId: data.conversation_id,
                        finalResult: true,
                    };
                    setMessages((prev) => {
                        const lastMsg = prev[prev.length - 1];
                        if (
                            lastMsg?.role === "assistant" &&
                            lastMsg.finalResult
                        ) {
                            return prev;
                        }
                        return [...prev, assistantMessage];
                    });
                }

                // 폴링 중지 로직
                if (
                    data.status === "completed" ||
                    data.status === "partially_completed"
                ) {
                    if (additionalPollsCount.current < maxAdditionalPolls) {
                        additionalPollsCount.current++;
                        console.log(
                            `완료 후 추가 폴링 (${additionalPollsCount.current}/${maxAdditionalPolls})`
                        );
                    } else {
                        console.log("모든 폴링 완료, 대화 쿼리 제거");
                        setWaitingForResponse(false);
                        removeConversationQuery();
                        queryClient.removeQueries([
                            "conversationStatus",
                            conversationId,
                        ]);
                    }
                }
            },
        }
    );

    const resetStatusPolling = () => {
        additionalPollsCount.current = 0;
        setConversationStatus(null);
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim() || queryMutation.isLoading) return;

        const currentConversationId =
            conversationId || generateConversationId();
        if (!conversationId) {
            setConversationId(currentConversationId);
        }

        const userMessage: Message = {
            role: "user",
            content: query,
            timestamp: new Date(),
            conversationId: currentConversationId,
        };
        setMessages((prev) => [...prev, userMessage]);

        const request: QueryRequest = {
            query: query.trim(),
            conversation_id: currentConversationId,
        };

        queryMutation.mutate(request);

        setQuery("");
        setWaitingForResponse(true);
        resetStatusPolling();
        eventEmitter.emit("querySubmitted", {});
    };

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, conversationStatus]);

    return (
        <div className="flex flex-col h-full bg-gray-50 p-4">
            <div
                ref={scrollRef}
                className="flex-grow overflow-y-auto space-y-4 mb-4 pr-2"
            >
                {messages.map((msg, index) => (
                    <div
                        key={`${msg.role}-${msg.timestamp.getTime()}-${index}`}
                        className={`flex ${
                            msg.role === "user"
                                ? "justify-end"
                                : "justify-start"
                        }`}
                    >
                        <div
                            className={`max-w-lg px-4 py-2 rounded-lg shadow-md ${
                                msg.role === "user"
                                    ? "bg-blue-500 text-white"
                                    : "bg-white text-gray-800"
                            }`}
                        >
                            <ReactMarkdown>{msg.content}</ReactMarkdown>
                            <div
                                className={`text-xs mt-1 ${
                                    msg.role === "user"
                                        ? "text-blue-100 text-right"
                                        : "text-gray-400 text-left"
                                }`}
                            >
                                {msg.timestamp.toLocaleTimeString([], {
                                    hour: "2-digit",
                                    minute: "2-digit",
                                })}
                            </div>
                        </div>
                    </div>
                ))}

                {/* 진행 중 메시지 및 태스크 상태 표시 */}
                {(waitingForResponse || queryMutation.isLoading) &&
                    conversationStatus &&
                    conversationStatus.tasks &&
                    conversationStatus.tasks.map((task, index) => {
                        // 태스크 타임스탬프 결정
                        const taskTimestamp = task.completed_at
                            ? new Date(task.completed_at * 1000) // 완료 시간 사용
                            : task.created_at
                            ? new Date(task.created_at * 1000) // 생성 시간 사용
                            : new Date(); // 둘 다 없으면 현재 시간

                        return (
                            <ProcessMessage
                                key={task.id || `ta***REMOVED***${index}`}
                                type={
                                    task.status === "completed"
                                        ? "agent_result"
                                        : "agent_processing"
                                }
                                role={task.role}
                                content={
                                    task.status === "completed"
                                        ? JSON.stringify(
                                              task.result || "결과 없음"
                                          )
                                        : `${
                                              task.description || "작업"
                                          } 처리 중...`
                                }
                                timestamp={taskTimestamp}
                                taskDescription={task.description}
                                taskIndex={task.index}
                            />
                        );
                    })}
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
                        {queryMutation.isLoading ? (
                            <span>전송 중...</span>
                        ) : (
                            <span>전송</span>
                        )}
                    </button>
                </div>
            </form>

            {/* 에러 메시지 표시 */}
            {queryMutation.isError && (
                <div className="mt-4 text-red-600 text-sm">
                    요청 처리 중 오류가 발생했습니다. 다시 시도해주세요.
                </div>
            )}
        </div>
    );
};

export default RequestForm;
