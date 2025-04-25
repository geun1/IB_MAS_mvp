import React from "react";
import { useQuery } from "react-query";
import { orchestratorApi } from "../api/orchestrator";
import { TaskStatus } from "../types";

interface TaskMonitorProps {
    taskId: string | null;
    className?: string;
}

interface Task {
    id: string;
    status: string;
    description?: string;
}

const TaskMonitor: React.FC<TaskMonitorProps> = ({
    taskId,
    className = "",
}) => {
    // 태스크 상태 조회 (conversation_id를 사용)
    const {
        data: conversation,
        isLoading,
        isError,
    } = useQuery(
        ["conversation", taskId],
        () => orchestratorApi.getConversationStatus(taskId || ""),
        {
            enabled: !!taskId,
            refetchInterval: taskId ? 2000 : false, // 2초마다 갱신
        }
    );

    // 로딩 중 표시
    if (isLoading) {
        return (
            <div className={`bg-white rounded-lg shadow-md p-4 ${className}`}>
                <div className="flex items-center justify-center">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
                    <span className="ml-2">태스크 상태 확인 중...</span>
                </div>
            </div>
        );
    }

    // 에러 표시
    if (isError) {
        return (
            <div className={`bg-white rounded-lg shadow-md p-4 ${className}`}>
                <div className="text-red-600">
                    태스크 상태를 가져오는 중 오류가 발생했습니다.
                </div>
            </div>
        );
    }

    // 태스크가 없는 경우
    if (!conversation) {
        return null;
    }

    return (
        <div className={`bg-white rounded-lg shadow-md p-4 ${className}`}>
            <h3 className="text-lg font-semibold mb-2">태스크 진행 상황</h3>

            {/* 전체 상태 */}
            <div className="mb-4">
                <div className="flex items-center">
                    <span className="font-medium mr-2">상태:</span>
                    <span
                        className={`px-2 py-1 rounded-full text-sm ${getStatusStyle(
                            conversation.status
                        )}`}
                    >
                        {getStatusText(conversation.status)}
                    </span>
                </div>
            </div>

            {/* 개별 태스크 목록 */}
            <div className="space-y-2">
                {/* tasks가 undefined인 경우 빈 배열로 대체 */}
                {(conversation.tasks || []).map((task: Task, index: number) => (
                    <div
                        key={task.id || `ta***REMOVED***${index}`}
                        className="border rounded p-2 bg-gray-50"
                    >
                        <div className="flex justify-between items-center">
                            <span className="font-medium">
                                태스크 {index + 1}
                            </span>
                            <span
                                className={`px-2 py-1 rounded-full text-sm ${getStatusStyle(
                                    task.status
                                )}`}
                            >
                                {getStatusText(task.status)}
                            </span>
                        </div>
                        {/* description이 있는 경우에만 표시 */}
                        {task.description && (
                            <p className="text-sm text-gray-600 mt-1">
                                {task.description}
                            </p>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
};

// 상태에 따른 스타일
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

// 상태 텍스트
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

export default TaskMonitor;
