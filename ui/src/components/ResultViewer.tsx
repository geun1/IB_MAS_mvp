import React, { useState, useEffect } from "react";
import { useQuery } from "react-query";
import { brokerApi } from "../api/broker";
import { TaskStatus } from "../types";

interface ResultViewerProps {
    taskId: string | null;
    className?: string;
}

const ResultViewer: React.FC<ResultViewerProps> = ({
    taskId,
    className = "",
}) => {
    // 최근 태스크 ID 기록
    const [recentTaskIds, setRecentTaskIds] = useState<string[]>(() => {
        try {
            const saved = localStorage.getItem("recentTaskIds");
            if (!saved) return [];

            const parsed = JSON.parse(saved);
            // 문자열 배열인지 확인하고 필터링
            return Array.isArray(parsed)
                ? parsed.filter((id): id is string => typeof id === "string")
                : [];
        } catch (error) {
            console.error("태스크 ID 목록 로드 중 오류:", error);
            return [];
        }
    });

    // 선택된 태스크 인덱스 (현재 보고 있는 태스크)
    const [selectedTaskIndex, setSelectedTaskIndex] = useState<number | null>(
        null
    );

    // 대화 ID로 태스크 목록을 조회
    const {
        data: conversationTasks,
        isLoading: isLoadingConversationTasks,
        error: conversationTasksError,
    } = useQuery(
        ["tasks-by-conversation", taskId],
        () => brokerApi.getTasksByConversation(taskId || "", 1, 10),
        {
            enabled: !!taskId,
            refetchInterval: taskId ? 2000 : false,
        }
    );

    // 태스크 목록에서 첫 번째 태스크 또는 완료된 태스크를 선택
    useEffect(() => {
        if (conversationTasks?.tasks && conversationTasks.tasks.length > 0) {
            console.log("태스크 목록:", conversationTasks.tasks);

            // 완료된 태스크가 있는지 확인
            const completedTaskIndex = conversationTasks.tasks.findIndex(
                (task) => task.status === "completed"
            );

            // 완료된 태스크가 있으면 해당 태스크를, 없으면 첫 번째 태스크 선택
            const newSelectedIndex =
                completedTaskIndex >= 0 ? completedTaskIndex : 0;
            setSelectedTaskIndex(newSelectedIndex);

            // 최근 태스크 목록 업데이트 - 대화 ID 대신 실제 태스크 ID 저장
            const taskId = conversationTasks.tasks[newSelectedIndex].task_id;
            if (taskId) {
                updateRecentTasks(taskId);
            }
        }
    }, [conversationTasks]);

    // 최근 태스크 목록 업데이트
    const updateRecentTasks = (taskId: string) => {
        setRecentTaskIds((prev) => {
            const updated = [
                taskId,
                ...prev.filter((id) => id !== taskId),
            ].slice(0, 5);
            localStorage.setItem("recentTaskIds", JSON.stringify(updated));
            return updated;
        });
    };

    // 상태에 따른 스타일 반환
    const getStatusStyle = (status: string) => {
        switch (status) {
            case "completed":
                return "bg-green-100 text-green-800";
            case "processing":
                return "bg-blue-100 text-blue-800";
            case "failed":
                return "bg-red-100 text-red-800";
            default:
                return "bg-gray-100 text-gray-800";
        }
    };

    // 상태 텍스트 반환
    const getStatusText = (status: string) => {
        switch (status) {
            case "completed":
                return "완료";
            case "processing":
                return "처리 중";
            case "failed":
                return "실패";
            default:
                return "대기 중";
        }
    };

    // 태스크 세부 정보 렌더링
    const renderTaskDetails = () => {
        // 태스크 목록이 있고 선택된 태스크 인덱스가 유효한 경우
        if (
            conversationTasks?.tasks &&
            selectedTaskIndex !== null &&
            selectedTaskIndex >= 0 &&
            selectedTaskIndex < conversationTasks.tasks.length
        ) {
            const task = conversationTasks.tasks[selectedTaskIndex];

            return (
                <div className="bg-white p-4 rounded-lg shadow-md">
                    <h3 className="text-lg font-semibold">
                        {task.role} 태스크 결과
                    </h3>
                    <div className="mt-2">
                        <p
                            className={`text-sm px-2 py-1 rounded inline-block ${getStatusStyle(
                                task.status
                            )}`}
                        >
                            {getStatusText(task.status)}
                        </p>
                    </div>
                    {task.result && (
                        <div className="mt-4 prose max-w-none">
                            {typeof task.result === "string" ? (
                                <div
                                    dangerouslySetInnerHTML={{
                                        __html: task.result,
                                    }}
                                />
                            ) : task.result.content ? (
                                <div
                                    dangerouslySetInnerHTML={{
                                        __html: task.result.content,
                                    }}
                                />
                            ) : (
                                <pre>
                                    {JSON.stringify(task.result, null, 2)}
                                </pre>
                            )}
                        </div>
                    )}
                </div>
            );
        }

        return null;
    };

    // 태스크가 선택되지 않은 경우
    if (!taskId && recentTaskIds.length === 0) {
        return (
            <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
                <h2 className="text-xl font-bold mb-4">태스크 결과</h2>
                <p className="text-gray-500">
                    표시할 결과가 없습니다. 새로운 요청을 생성해주세요.
                </p>
            </div>
        );
    }

    // 로딩 중인 경우
    if (isLoadingConversationTasks) {
        return (
            <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
                <h2 className="text-xl font-bold mb-4">태스크 결과</h2>
                <div className="flex items-center justify-center p-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    <span className="ml-2">결과 로딩 중...</span>
                </div>
            </div>
        );
    }

    // 오류가 있는 경우
    if (conversationTasksError) {
        return (
            <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
                <h2 className="text-xl font-bold mb-4">태스크 결과</h2>
                <div className="bg-red-50 text-red-600 p-4 rounded-md">
                    <p>결과를 가져오는 중 오류가 발생했습니다.</p>
                </div>
            </div>
        );
    }

    return (
        <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
            <div className="flex justify-between items-start mb-4">
                <h2 className="text-xl font-bold">태스크 결과</h2>

                {/* 다른 태스크 선택 드롭다운 */}
                {conversationTasks?.tasks &&
                    conversationTasks.tasks.length > 1 && (
                        <div className="relative inline-block text-left">
                            <select
                                className="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
                                value={
                                    selectedTaskIndex !== null
                                        ? selectedTaskIndex
                                        : 0
                                }
                                onChange={(e) =>
                                    setSelectedTaskIndex(Number(e.target.value))
                                }
                            >
                                {conversationTasks.tasks.map((task, index) => (
                                    <option key={task.task_id} value={index}>
                                        {task.role} (
                                        {getStatusText(task.status)})
                                    </option>
                                ))}
                            </select>
                        </div>
                    )}
            </div>

            {renderTaskDetails()}
        </div>
    );
};

export default ResultViewer;
