import React, { useState, useEffect } from "react";
import { useQuery } from "react-query";
import { orchestratorApi } from "../api/orchestrator";
import { format } from "date-fns";
import ReactMarkdown from "react-markdown";
import {
    ConversationListItem,
    ConversationDetail,
    Message,
} from "../types/messages";

const ConversationList: React.FC = () => {
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<"detail" | "messages">("detail");

    // 대화 목록 조회
    const {
        data: conversations,
        isLoading,
        isError,
        refetch,
    } = useQuery<ConversationListItem[]>(
        "conversations",
        orchestratorApi.listConversations,
        {
            refetchInterval: 10000,
        }
    );

    // 대화 상세 정보 조회
    const { data: detail, isLoading: isDetailLoading } =
        useQuery<ConversationDetail>(
            ["conversationDetail", selectedId],
            () => orchestratorApi.getConversationDetail(selectedId || ""),
            { enabled: !!selectedId }
        );

    // 대화 메시지 목록 조회
    const { data: messages, isLoading: isMessagesLoading } = useQuery<
        Message[]
    >(
        ["conversationMessages", selectedId],
        () => orchestratorApi.getConversationMessages(selectedId || ""),
        { enabled: !!selectedId }
    );

    // 시간 포맷팅 함수
    const formatTime = (timestamp: number) => {
        if (!timestamp) return "-";
        return format(new Date(timestamp * 1000), "yyyy-MM-dd HH:mm:ss");
    };

    // 복잡한 task.id 객체 처리를 위한 함수 추가
    const extractTaskId = (task: any): string => {
        if (!task || !task.id) return "unknown-id";

        if (typeof task.id === "string") {
            return task.id;
        } else if (typeof task.id === "object") {
            return (
                task.id.task_id ||
                JSON.stringify(task.id).substring(0, 10) + "..."
            );
        }

        return String(task.id);
    };

    return (
        <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold mb-4">대화 목록</h2>

            <div className="mb-4">
                <button
                    onClick={() => refetch()}
                    className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                >
                    새로고침
                </button>
            </div>

            {isLoading ? (
                <div className="text-center py-4">로딩 중...</div>
            ) : isError ? (
                <div className="text-red-500 py-4">
                    대화 목록을 불러오는 중 오류가 발생했습니다.
                </div>
            ) : !conversations || conversations.length === 0 ? (
                <div className="text-gray-500 py-4">대화 내역이 없습니다.</div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* 대화 목록 */}
                    <div className="lg:col-span-1 border rounded-lg overflow-hidden">
                        <div className="bg-gray-100 px-4 py-2 font-medium border-b">
                            최근 대화 목록
                        </div>
                        <div className="divide-y max-h-[500px] overflow-auto">
                            {conversations.map((conv) => (
                                <div
                                    key={conv.conversation_id}
                                    className={`px-4 py-3 cursor-pointer hover:bg-gray-50 ${
                                        selectedId === conv.conversation_id
                                            ? "bg-blue-50"
                                            : ""
                                    }`}
                                    onClick={() => {
                                        setSelectedId(conv.conversation_id);
                                        setActiveTab("detail"); // 기본 탭을 상세 정보로 설정
                                    }}
                                >
                                    <div className="font-medium truncate">
                                        {conv.query || "제목 없음"}
                                    </div>
                                    <div className="flex justify-between text-sm text-gray-500 mt-1">
                                        <span>태스크: {conv.task_count}개</span>
                                        <span>
                                            {formatTime(conv.created_at)}
                                        </span>
                                    </div>
                                    <div className="mt-1">
                                        <span
                                            className={`px-2 py-0.5 text-xs rounded-full ${
                                                conv.status === "completed"
                                                    ? "bg-green-100 text-green-800"
                                                    : conv.status ===
                                                      "processing"
                                                    ? "bg-blue-100 text-blue-800"
                                                    : "bg-gray-100 text-gray-800"
                                            }`}
                                        >
                                            {conv.status === "completed"
                                                ? "완료"
                                                : conv.status === "processing"
                                                ? "처리 중"
                                                : conv.status}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* 대화 상세 정보 */}
                    <div className="lg:col-span-2 border rounded-lg overflow-hidden">
                        {!selectedId ? (
                            <div className="p-8 text-center text-gray-500">
                                왼쪽 목록에서 대화를 선택하세요
                            </div>
                        ) : (
                            <div>
                                {/* 대화 헤더 */}
                                <div className="bg-gray-100 px-4 py-3 border-b">
                                    <h3 className="font-semibold">
                                        {detail?.query || "제목 없음"}
                                    </h3>
                                    <div className="flex justify-between text-sm mt-1">
                                        <span>ID: {selectedId}</span>
                                        <span>
                                            생성:{" "}
                                            {detail?.created_at
                                                ? formatTime(detail.created_at)
                                                : "-"}
                                        </span>
                                    </div>
                                </div>

                                {/* 탭 메뉴 */}
                                <div className="flex border-b">
                                    <button
                                        className={`px-4 py-2 text-sm font-medium ${
                                            activeTab === "detail"
                                                ? "border-b-2 border-blue-500 text-blue-600"
                                                : "text-gray-500 hover:text-gray-700"
                                        }`}
                                        onClick={() => setActiveTab("detail")}
                                    >
                                        통합 결과
                                    </button>
                                    <button
                                        className={`px-4 py-2 text-sm font-medium ${
                                            activeTab === "messages"
                                                ? "border-b-2 border-blue-500 text-blue-600"
                                                : "text-gray-500 hover:text-gray-700"
                                        }`}
                                        onClick={() => setActiveTab("messages")}
                                    >
                                        메시지 기록
                                    </button>
                                </div>

                                {/* 대화 내용 */}
                                <div className="p-4 max-h-[600px] overflow-auto">
                                    {activeTab === "detail" ? (
                                        // 통합 결과 탭
                                        isDetailLoading ? (
                                            <div className="p-8 text-center">
                                                <div className="animate-spin inline-block w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full"></div>
                                                <div className="mt-2">
                                                    상세 정보 로딩 중...
                                                </div>
                                            </div>
                                        ) : !detail ? (
                                            <div className="p-8 text-center text-red-500">
                                                대화 정보를 불러올 수 없습니다
                                            </div>
                                        ) : (
                                            <div>
                                                {/* 통합 결과 */}
                                                <div className="mb-6">
                                                    <h4 className="font-semibold text-lg border-b pb-2 mb-3">
                                                        통합 결과
                                                    </h4>
                                                    <div className="whitespace-pre-wrap bg-gray-50 p-4 rounded">
                                                        {detail.message ||
                                                            "결과가 없습니다."}
                                                    </div>
                                                </div>

                                                {/* 에이전트별 결과 */}
                                                <div className="mb-6">
                                                    <h4 className="font-semibold text-lg border-b pb-2 mb-3">
                                                        에이전트별 결과 (
                                                        {detail.tasks?.length ||
                                                            0}
                                                        개)
                                                    </h4>
                                                    <div className="space-y-4">
                                                        {detail.tasks?.map(
                                                            (
                                                                task: any,
                                                                index: number
                                                            ) => (
                                                                <div
                                                                    key={index}
                                                                    className="border rounded-lg overflow-hidden"
                                                                >
                                                                    <div className="bg-gray-50 px-4 py-2 flex justify-between items-center">
                                                                        <div>
                                                                            <span className="font-medium">
                                                                                {task.role ||
                                                                                    "알 수 없는 태스크"}
                                                                            </span>
                                                                            <span
                                                                                className={`ml-2 px-2 py-0.5 text-xs rounded-full ${
                                                                                    task.status ===
                                                                                    "completed"
                                                                                        ? "bg-green-100 text-green-800"
                                                                                        : "bg-gray-100 text-gray-800"
                                                                                }`}
                                                                            >
                                                                                {
                                                                                    task.status
                                                                                }
                                                                            </span>
                                                                        </div>
                                                                        <div className="text-sm text-gray-500">
                                                                            {task.completed_at
                                                                                ? formatTime(
                                                                                      task.completed_at
                                                                                  )
                                                                                : "-"}
                                                                        </div>
                                                                    </div>
                                                                    <div className="p-3 text-sm">
                                                                        <div className="mb-2">
                                                                            <span className="font-medium">
                                                                                태스크
                                                                                ID:
                                                                            </span>{" "}
                                                                            {extractTaskId(
                                                                                task
                                                                            )}
                                                                        </div>
                                                                        <div className="mb-2">
                                                                            <span className="font-medium">
                                                                                설명:
                                                                            </span>{" "}
                                                                            {task.description ||
                                                                                "설명 없음"}
                                                                        </div>
                                                                        {task.result && (
                                                                            <div>
                                                                                <div className="font-medium mb-1">
                                                                                    결과:
                                                                                </div>
                                                                                {typeof task.result ===
                                                                                    "object" &&
                                                                                task
                                                                                    .result
                                                                                    .data ? (
                                                                                    // stock_data_agent 타입의 결과 처리 (data 객체)
                                                                                    <pre className="whitespace-pre-wrap bg-gray-50 p-3 rounded text-sm overflow-x-auto">
                                                                                        {JSON.stringify(
                                                                                            task
                                                                                                .result
                                                                                                .data,
                                                                                            null,
                                                                                            2
                                                                                        )}
                                                                                    </pre>
                                                                                ) : typeof task.result ===
                                                                                      "object" &&
                                                                                  task
                                                                                      .result
                                                                                      .result &&
                                                                                  task
                                                                                      .result
                                                                                      .result
                                                                                      .content ? (
                                                                                    // 중첩 구조: result.result.content
                                                                                    <div className="whitespace-pre-wrap bg-gray-50 p-3 rounded text-sm">
                                                                                        {
                                                                                            task
                                                                                                .result
                                                                                                .result
                                                                                                .content
                                                                                        }
                                                                                    </div>
                                                                                ) : typeof task.result ===
                                                                                      "object" &&
                                                                                  task
                                                                                      .result
                                                                                      .result &&
                                                                                  task
                                                                                      .result
                                                                                      .result
                                                                                      .message ? (
                                                                                    // 중첩 구조: result.result.message
                                                                                    <div className="whitespace-pre-wrap bg-gray-50 p-3 rounded text-sm">
                                                                                        {
                                                                                            task
                                                                                                .result
                                                                                                .result
                                                                                                .message
                                                                                        }
                                                                                    </div>
                                                                                ) : typeof task.result ===
                                                                                      "object" &&
                                                                                  task
                                                                                      .result
                                                                                      .content ? (
                                                                                    // 중첩 구조: result.content
                                                                                    <div className="whitespace-pre-wrap bg-gray-50 p-3 rounded text-sm">
                                                                                        {
                                                                                            task
                                                                                                .result
                                                                                                .content
                                                                                        }
                                                                                    </div>
                                                                                ) : typeof task.result ===
                                                                                      "object" &&
                                                                                  task
                                                                                      .result
                                                                                      .message ? (
                                                                                    // 중첩 구조: result.message
                                                                                    <div className="whitespace-pre-wrap bg-gray-50 p-3 rounded text-sm">
                                                                                        {
                                                                                            task
                                                                                                .result
                                                                                                .message
                                                                                        }
                                                                                    </div>
                                                                                ) : typeof task.result ===
                                                                                  "string" ? (
                                                                                    // 문자열 결과
                                                                                    <div className="whitespace-pre-wrap bg-gray-50 p-3 rounded text-sm">
                                                                                        {
                                                                                            task.result
                                                                                        }
                                                                                    </div>
                                                                                ) : (
                                                                                    // 기타 객체 형태의 결과는 JSON으로 표시
                                                                                    <pre className="whitespace-pre-wrap bg-gray-50 p-3 rounded text-sm overflow-x-auto">
                                                                                        {JSON.stringify(
                                                                                            task.result,
                                                                                            null,
                                                                                            2
                                                                                        )}
                                                                                    </pre>
                                                                                )}
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                </div>
                                                            )
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        )
                                    ) : // 메시지 기록 탭
                                    isMessagesLoading ? (
                                        <div className="p-8 text-center">
                                            <div className="animate-spin inline-block w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full"></div>
                                            <div className="mt-2">
                                                메시지 기록 로딩 중...
                                            </div>
                                        </div>
                                    ) : !messages || messages.length === 0 ? (
                                        <div className="p-8 text-center text-gray-500">
                                            메시지 기록이 없습니다
                                        </div>
                                    ) : (
                                        <div className="space-y-6">
                                            <h4 className="font-semibold text-lg border-b pb-2">
                                                대화 기록 ({messages.length}개
                                                메시지)
                                            </h4>

                                            <div className="space-y-4">
                                                {messages.map(
                                                    (message, index) => (
                                                        <div
                                                            key={index}
                                                            className="border rounded-lg overflow-hidden"
                                                        >
                                                            <div className="bg-gray-50 px-4 py-2 flex justify-between items-center">
                                                                <div className="font-medium">
                                                                    {message.id
                                                                        ? `메시지 ID: ${message.id.substring(
                                                                              0,
                                                                              8
                                                                          )}...`
                                                                        : "메시지"}
                                                                </div>
                                                                <div className="text-sm text-gray-500">
                                                                    {message.created_at
                                                                        ? formatTime(
                                                                              message.created_at
                                                                          )
                                                                        : message.timestamp
                                                                        ? message.timestamp.toLocaleString()
                                                                        : "-"}
                                                                </div>
                                                            </div>
                                                            <div className="p-4">
                                                                <div className="mb-3 grid grid-cols-1 md:grid-cols-2 gap-4">
                                                                    <div>
                                                                        <h5 className="text-sm font-medium text-gray-700 mb-1">
                                                                            요청:
                                                                        </h5>
                                                                        <div className="bg-gray-50 p-3 rounded text-sm whitespace-pre-wrap">
                                                                            {message.request ||
                                                                                message.content ||
                                                                                "요청 내용 없음"}
                                                                        </div>
                                                                    </div>
                                                                    {(message.response ||
                                                                        message.role ===
                                                                            "assistant") && (
                                                                        <div>
                                                                            <h5 className="text-sm font-medium text-gray-700 mb-1">
                                                                                응답:
                                                                            </h5>
                                                                            <div className="bg-gray-50 p-3 rounded text-sm whitespace-pre-wrap">
                                                                                <ReactMarkdown>
                                                                                    {message.response ||
                                                                                        message.content ||
                                                                                        "응답 내용 없음"}
                                                                                </ReactMarkdown>
                                                                            </div>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                                <div className="flex justify-between text-xs text-gray-500 mt-2">
                                                                    <span>
                                                                        상태:{" "}
                                                                        {message.status ||
                                                                            "완료"}
                                                                    </span>
                                                                    <span>
                                                                        유형:{" "}
                                                                        {message.role ||
                                                                            "사용자"}
                                                                    </span>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    )
                                                )}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default ConversationList;
