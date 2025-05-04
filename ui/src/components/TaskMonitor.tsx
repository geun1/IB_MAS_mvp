import React, { useState, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "react-query";
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
    const [debugInfo, setDebugInfo] = useState<string>("");
    const [taskCompleted, setTaskCompleted] = useState<boolean>(false);
    const [expandedTasks, setExpandedTasks] = useState<number[]>([]); // 확장된 태스크 인덱스 추적

    // 폴링 제어 변수
    const lastPollingTime = useRef<number>(0);
    const pollingInterval = 3000; // 3초
    const maxAdditionalPolls = 1;
    const additionalPollsCount = useRef<number>(0);

    // 쿼리 클라이언트
    const queryClient = useQueryClient();

    // 대화 상태 조회
    const {
        data,
        isLoading,
        isError,
        error,
        remove: removeTaskQuery,
    } = useQuery(
        ["conversationStatus", taskId],
        () => {
            // 현재 시간 체크
            const currentTime = Date.now();

            // 마지막 폴링 이후 충분한 시간이 지났는지 확인
            if (currentTime - lastPollingTime.current < pollingInterval) {
                console.log("TaskMonitor - 폴링 간격 유지 중...");
                return Promise.resolve(null);
            }

            // 폴링 시간 업데이트
            lastPollingTime.current = currentTime;

            // API 호출
            return taskId
                ? orchestratorApi.getConversationStatus(taskId)
                : null;
        },
        {
            enabled: !!taskId && !taskCompleted,
            refetchInterval: !taskCompleted ? pollingInterval : false,
            onSuccess: (data) => {
                if (!data) return;

                console.log("TaskMonitor - 대화 상태 데이터:", data);
                if (data.tasks) {
                    console.log("태스크 개수:", data.tasks.length);
                    setDebugInfo("");

                    // 모든 태스크가 완료되었는지 확인 (completed, failed 등의 최종 상태)
                    if (
                        data.status === "completed" ||
                        data.status === "failed" ||
                        data.status === "partially_completed"
                    ) {
                        // 최대 1번의 추가 폴링 허용 (누락된 결과 확인용)
                        if (additionalPollsCount.current < maxAdditionalPolls) {
                            additionalPollsCount.current++;
                            console.log(
                                `TaskMonitor - 완료 후 추가 폴링 (${additionalPollsCount.current}/${maxAdditionalPolls})`
                            );
                        } else {
                            console.log("TaskMonitor - 폴링 완전히 중지");
                            setTaskCompleted(true);
                            removeTaskQuery();

                            // 캐시에서도 제거
                            queryClient.removeQueries([
                                "conversationStatus",
                                taskId,
                            ]);
                        }
                    }
                }
            },
            onError: (err: any) => {
                console.error("TaskMonitor - 데이터 조회 오류:", err);
                setDebugInfo(
                    JSON.stringify(
                        err?.response?.data ||
                            err?.message ||
                            "알 수 없는 오류",
                        null,
                        2
                    )
                );
            },
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

    // 컴포넌트 마운트 시 폴링 시간 초기화
    useEffect(() => {
        if (taskId) {
            lastPollingTime.current = Date.now();
            additionalPollsCount.current = 0;
            setTaskCompleted(false);
            setExpandedTasks([]); // 새 태스크 시작시 확장된 태스크 목록 초기화
        }
    }, [taskId]);

    // 태스크 클릭 핸들러
    const handleTaskClick = (taskId: string) => {
        setSelectedTaskId(taskId);
        setShowTaskDetails(true);
    };

    // 태스크 드롭다운 토글 핸들러
    const toggleTaskExpansion = (index: number) => {
        setExpandedTasks((prev) =>
            prev.includes(index)
                ? prev.filter((i) => i !== index)
                : [...prev, index]
        );
    };

    // 모달 닫기 핸들러
    const closeTaskDetails = () => {
        setShowTaskDetails(false);
    };

    // 결과 추출 함수
    const extractTaskResult = (task: any): string => {
        if (!task) return "";

        console.log("태스크 결과 추출:", task);

        try {
            // 결과가 없는 경우
            if (!task.result) {
                return "결과 정보가 없습니다.";
            }

            // stock_data_agent 결과 구조 처리 (data 객체)
            if (typeof task.result === "object" && task.result.data) {
                console.log("stock_data_agent 구조 감지: result.data");
                return `주식 데이터 결과:\n\`\`\`json\n${JSON.stringify(
                    task.result.data,
                    null,
                    2
                )}\n\`\`\``;
            }

            // 결과가 직접 문자열인 경우
            if (typeof task.result === "string") {
                console.log("태스크 결과가 직접 문자열");
                return task.result;
            }

            // 중첩된 구조: result > result > content
            if (
                typeof task.result === "object" &&
                task.result.result &&
                typeof task.result.result === "object" &&
                task.result.result.content
            ) {
                console.log("태스크 결과 구조: result.result.content");
                return String(task.result.result.content);
            }

            // 중첩된 구조: result > content
            if (typeof task.result === "object" && task.result.content) {
                console.log("태스크 결과 구조: result.content");
                return String(task.result.content);
            }

            // 중첩된 구조: result > result > message
            if (
                typeof task.result === "object" &&
                task.result.result &&
                typeof task.result.result === "object" &&
                task.result.result.message
            ) {
                console.log("태스크 결과 구조: result.result.message");
                return String(task.result.result.message);
            }

            // 중첩된 구조: result > message
            if (typeof task.result === "object" && task.result.message) {
                console.log("태스크 결과 구조: result.message");
                return String(task.result.message);
            }

            // 중첩된 구조: result > result (문자열)
            if (
                typeof task.result === "object" &&
                task.result.result &&
                typeof task.result.result === "string"
            ) {
                console.log("태스크 결과 구조: result.result (문자열)");
                return task.result.result;
            }

            // 중첩된 구조: result > result (객체)
            if (
                typeof task.result === "object" &&
                task.result.result &&
                typeof task.result.result === "object"
            ) {
                console.log("태스크 결과 구조: result.result (객체)");
                return JSON.stringify(task.result.result, null, 2);
            }

            // 기본: result 객체 전체를 JSON으로 변환
            if (typeof task.result === "object") {
                console.log("태스크 결과 구조: result (객체)");
                return JSON.stringify(task.result, null, 2);
            }

            return "결과 형식을 해석할 수 없습니다.";
        } catch (error) {
            console.error("태스크 결과 추출 중 오류:", error);
            return "결과 추출 중 오류가 발생했습니다.";
        }
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
                                    <div className="bg-gray-50 p-4 rounded-md overflow-x-auto prose prose-sm max-w-none">
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
                    {debugInfo && (
                        <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-x-auto">
                            {debugInfo}
                        </pre>
                    )}
                </div>
            </div>
        );
    }

    // 태스크가 없거나 데이터가 없는 경우
    if (!data || !data.tasks || data.tasks.length === 0) {
        return (
            <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
                <h3 className="text-lg font-semibold mb-4">태스크 진행 상황</h3>
                <div className="text-gray-500 p-4">
                    처리 중인 태스크가 없습니다.
                </div>
                {data && (
                    <div className="mt-2 text-sm">
                        <div>대화 ID: {data.conversation_id}</div>
                        <div>상태: {data.status}</div>
                        {data.message && (
                            <div className="mt-2">
                                <span className="font-medium">메시지:</span>{" "}
                                {data.message}
                            </div>
                        )}
                    </div>
                )}
            </div>
        );
    }

    // 태스크 목록 표시
    return (
        <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
            <h3 className="text-lg font-semibold mb-4">태스크 진행 상황</h3>
            <div className="space-y-2">
                {data.tasks.map((task: any, index: number) => (
                    <div
                        key={index}
                        className="border rounded-md overflow-hidden"
                    >
                        <div
                            className="bg-gray-50 p-3 cursor-pointer hover:bg-gray-100 transition-colors flex items-center justify-between"
                            onClick={() => toggleTaskExpansion(index)}
                        >
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
                            <div className="flex items-center">
                                <span className="text-sm text-gray-500 mr-2">
                                    {typeof task === "string"
                                        ? task.substring(0, 8) + "..."
                                        : task.status || "불명"}
                                </span>
                                <svg
                                    className={`w-4 h-4 transition-transform ${
                                        expandedTasks.includes(index)
                                            ? "transform rotate-180"
                                            : ""
                                    }`}
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth="2"
                                        d="M19 9l-7 7-7-7"
                                    />
                                </svg>
                            </div>
                        </div>

                        {expandedTasks.includes(index) && (
                            <div className="p-3 bg-white border-t">
                                <div className="text-sm text-gray-600 mb-2">
                                    {typeof task === "string"
                                        ? "설명 없음"
                                        : task.description || "설명 없음"}
                                </div>

                                {task.result && (
                                    <div className="mt-3">
                                        <div className="text-xs font-medium text-gray-500 mb-1">
                                            결과:
                                        </div>
                                        <div className="bg-gray-50 p-2 rounded text-xs overflow-x-auto prose prose-sm max-w-none">
                                            <ReactMarkdown>
                                                {extractTaskResult(task)}
                                            </ReactMarkdown>
                                        </div>
                                    </div>
                                )}

                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleTaskClick(task.id);
                                    }}
                                    className="mt-2 text-xs text-blue-500 hover:text-blue-700"
                                >
                                    상세 보기
                                </button>
                            </div>
                        )}
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
