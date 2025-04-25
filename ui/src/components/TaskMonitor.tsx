import React, { useState } from "react";
import { useQuery } from "react-query";
import { orchestratorApi } from "../api/orchestrator";
import { TaskStatus } from "../types";
import ReactMarkdown from "react-markdown";

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
    // 선택된 태스크 ID와 세부 정보 모달 상태
    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
    const [showTaskDetails, setShowTaskDetails] = useState<boolean>(false);

    // 대화 상태 조회
    const { data, isLoading, isError } = useQuery(
        ["conversationStatus", taskId],
        () => orchestratorApi.getConversationStatus(taskId || ""),
        {
            enabled: !!taskId,
            refetchInterval: taskId ? 3000 : false, // 3초마다 갱신
        }
    );

    // 선택된 태스크 세부 정보 조회
    const {
        data: taskDetail,
        isLoading: isTaskDetailLoading,
        isError: isTaskDetailError,
    } = useQuery(
        ["taskDetail", selectedTaskId],
        () => orchestratorApi.getConversationDetail(taskId || ""),
        {
            enabled: !!selectedTaskId && showTaskDetails,
            refetchInterval: false, // 자동 갱신 없음
        }
    );

    // 태스크 클릭 핸들러
    const handleTaskClick = (taskId: string) => {
        setSelectedTaskId(taskId);
        setShowTaskDetails(true);
    };

    // 모달 닫기 핸들러
    const closeTaskDetails = () => {
        setShowTaskDetails(false);
    };

    // 결과 추출 함수
    const extractTaskResult = (task: any): string => {
        if (!task) return "";

        // result가 객체이고 content 속성이 있는 경우
        if (
            task.result &&
            typeof task.result === "object" &&
            task.result.result
        ) {
            return (
                task.result.result.content ||
                JSON.stringify(task.result.result, null, 2)
            );
        }

        // result가 객체인 경우
        if (task.result && typeof task.result === "object") {
            return JSON.stringify(task.result, null, 2);
        }

        // result가 문자열인 경우
        return String(task.result || "");
    };

    // 태스크 세부 정보 모달
    const renderTaskDetailModal = () => {
        if (!showTaskDetails) return null;

        // 선택된 태스크 찾기
        const selectedTask = taskDetail?.tasks?.find(
            (t: any) => t.id === selectedTaskId
        );

        return (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                <div className="bg-white rounded-lg shadow-xl p-6 w-11/12 max-w-3xl max-h-[90vh] overflow-y-auto">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-xl font-semibold">
                            태스크 세부 정보
                        </h3>
                        <button
                            onClick={closeTaskDetails}
                            className="text-gray-500 hover:text-gray-800"
                        >
                            ×
                        </button>
                    </div>

                    {isTaskDetailLoading ? (
                        <div className="flex justify-center py-8">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                        </div>
                    ) : isTaskDetailError ? (
                        <div className="text-red-500 py-4">
                            태스크 정보를 불러오는 중 오류가 발생했습니다.
                        </div>
                    ) : selectedTask ? (
                        <div className="space-y-4">
                            <div>
                                <span className="font-medium">ID:</span>{" "}
                                {selectedTask.id}
                            </div>
                            <div>
                                <span className="font-medium">역할:</span>{" "}
                                {selectedTask.role || "없음"}
                            </div>
                            <div>
                                <span className="font-medium">상태:</span>{" "}
                                <span
                                    className={`px-2 py-1 rounded-full text-xs ${
                                        selectedTask.status === "completed"
                                            ? "bg-green-100 text-green-800"
                                            : selectedTask.status ===
                                              "processing"
                                            ? "bg-blue-100 text-blue-800"
                                            : selectedTask.status === "failed"
                                            ? "bg-red-100 text-red-800"
                                            : "bg-gray-100 text-gray-800"
                                    }`}
                                >
                                    {selectedTask.status}
                                </span>
                            </div>
                            <div>
                                <span className="font-medium">설명:</span>{" "}
                                {selectedTask.description || "없음"}
                            </div>
                            {selectedTask.result && (
                                <div>
                                    <div className="font-medium mb-2">
                                        결과:
                                    </div>
                                    <div className="bg-gray-50 p-4 rounded-md overflow-x-auto">
                                        <ReactMarkdown>
                                            {extractTaskResult(selectedTask)}
                                        </ReactMarkdown>
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="text-gray-500 py-4">
                            태스크 정보를 찾을 수 없습니다.
                        </div>
                    )}
                </div>
            </div>
        );
    };

    // 로딩 중 표시
    if (isLoading) {
        return (
            <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
                <h3 className="text-lg font-semibold mb-4">태스크 진행 상황</h3>
                <div className="flex items-center justify-center p-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    <span className="ml-2">태스크 정보 로딩 중...</span>
                </div>
            </div>
        );
    }

    // 오류 발생 시
    if (isError) {
        return (
            <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
                <h3 className="text-lg font-semibold mb-4">태스크 진행 상황</h3>
                <div className="text-red-500 p-4">
                    태스크 정보를 불러오는 중 오류가 발생했습니다.
                </div>
            </div>
        );
    }

    // 태스크가 없는 경우
    const tasks = data?.tasks || [];
    if (tasks.length === 0) {
        return (
            <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
                <h3 className="text-lg font-semibold mb-4">태스크 진행 상황</h3>
                <div className="text-gray-500 p-4">
                    진행 중인 태스크가 없습니다.
                </div>
            </div>
        );
    }

    // 태스크 목록 표시
    return (
        <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
            <h3 className="text-lg font-semibold mb-4">태스크 진행 상황</h3>
            <div className="space-y-2">
                {tasks.map((task: any, index: number) => (
                    <div
                        key={index}
                        className="border rounded-md p-3 hover:bg-gray-50 cursor-pointer transition-colors"
                        onClick={() => handleTaskClick(task)}
                    >
                        <div className="flex items-center justify-between">
                            <div className="flex items-center">
                                <span
                                    className={`inline-block w-3 h-3 rounded-full mr-2 ${
                                        task.status === "completed"
                                            ? "bg-green-500"
                                            : task.status === "processing"
                                            ? "bg-blue-500"
                                            : task.status === "failed"
                                            ? "bg-red-500"
                                            : "bg-gray-500"
                                    }`}
                                ></span>
                                <span className="font-medium text-gray-700">
                                    {typeof task === "string"
                                        ? `태스크 ${index + 1}`
                                        : task.role || `태스크 ${index + 1}`}
                                </span>
                            </div>
                            <span className="text-sm text-gray-500">
                                {typeof task === "string"
                                    ? task.substring(0, 8) + "..."
                                    : task.status || "불명"}
                            </span>
                        </div>
                        <div className="mt-1 text-sm text-gray-600 truncate">
                            {typeof task === "string"
                                ? "클릭하여 세부 정보 보기"
                                : task.description || "클릭하여 세부 정보 보기"}
                        </div>
                    </div>
                ))}
            </div>

            {/* 태스크 세부 정보 모달 */}
            {renderTaskDetailModal()}
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
