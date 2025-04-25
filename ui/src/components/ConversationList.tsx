import React, { useState } from "react";
import { useQuery } from "react-query";
import { orchestratorApi } from "../api/orchestrator";
import { format } from "date-fns";

const ConversationList: React.FC = () => {
    const [selectedId, setSelectedId] = useState<string | null>(null);

    // 대화 목록 조회
    const {
        data: conversations,
        isLoading,
        isError,
        refetch,
    } = useQuery("conversations", orchestratorApi.listConversations, {
        refetchInterval: 10000,
    });

    // 대화 상세 정보 조회
    const { data: detail, isLoading: isDetailLoading } = useQuery(
        ["conversationDetail", selectedId],
        () => orchestratorApi.getConversationDetail(selectedId || ""),
        { enabled: !!selectedId }
    );

    // 시간 포맷팅 함수
    const formatTime = (timestamp: number) => {
        if (!timestamp) return "-";
        return format(new Date(timestamp * 1000), "yyyy-MM-dd HH:mm:ss");
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
            ) : conversations?.length === 0 ? (
                <div className="text-gray-500 py-4">대화 내역이 없습니다.</div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* 대화 목록 */}
                    <div className="lg:col-span-1 border rounded-lg overflow-hidden">
                        <div className="bg-gray-100 px-4 py-2 font-medium border-b">
                            최근 대화 목록
                        </div>
                        <div className="divide-y max-h-[500px] overflow-auto">
                            {conversations?.map((conv) => (
                                <div
                                    key={conv.conversation_id}
                                    className={`px-4 py-3 cursor-pointer hover:bg-gray-50 ${
                                        selectedId === conv.conversation_id
                                            ? "bg-blue-50"
                                            : ""
                                    }`}
                                    onClick={() =>
                                        setSelectedId(conv.conversation_id)
                                    }
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
                        ) : isDetailLoading ? (
                            <div className="p-8 text-center">
                                <div className="animate-spin inline-block w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full"></div>
                                <div className="mt-2">상세 정보 로딩 중...</div>
                            </div>
                        ) : !detail ? (
                            <div className="p-8 text-center text-red-500">
                                대화 정보를 불러올 수 없습니다
                            </div>
                        ) : (
                            <div>
                                {/* 대화 헤더 */}
                                <div className="bg-gray-100 px-4 py-3 border-b">
                                    <h3 className="font-semibold">
                                        {detail.query || "제목 없음"}
                                    </h3>
                                    <div className="flex justify-between text-sm mt-1">
                                        <span>
                                            ID: {detail.conversation_id}
                                        </span>
                                        <span>
                                            생성:{" "}
                                            {formatTime(detail.created_at)}
                                        </span>
                                    </div>
                                </div>

                                {/* 대화 내용 */}
                                <div className="p-4 max-h-[600px] overflow-auto">
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
                                            {detail.tasks?.length || 0}개)
                                        </h4>
                                        <div className="space-y-4">
                                            {detail.tasks?.map((task: any) => (
                                                <div
                                                    key={task.id}
                                                    className="border rounded-lg overflow-hidden"
                                                >
                                                    <div className="bg-gray-50 px-4 py-2 flex justify-between items-center">
                                                        <div>
                                                            <span className="font-medium">
                                                                {task.agent
                                                                    ?.role ||
                                                                    task.description ||
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
                                                                {task.status}
                                                            </span>
                                                        </div>
                                                        <div className="text-sm text-gray-500">
                                                            {formatTime(
                                                                task.completed_at
                                                            )}
                                                        </div>
                                                    </div>
                                                    <div className="p-3 text-sm">
                                                        <div className="mb-2">
                                                            <span className="font-medium">
                                                                에이전트:
                                                            </span>{" "}
                                                            {task.agent?.name ||
                                                                task.agent
                                                                    ?.id ||
                                                                "정보 없음"}
                                                        </div>
                                                        <div className="mb-3">
                                                            <span className="font-medium">
                                                                설명:
                                                            </span>{" "}
                                                            {task.agent
                                                                ?.description ||
                                                                "설명 없음"}
                                                        </div>
                                                        <div>
                                                            <div className="font-medium mb-1">
                                                                결과:
                                                            </div>
                                                            <div className="whitespace-pre-wrap bg-gray-50 p-3 rounded text-sm">
                                                                {task.result
                                                                    ?.content ||
                                                                    "결과가 없습니다."}
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
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
