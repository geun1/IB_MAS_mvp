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

    // 선택된 태스크 ID (현재 보고 있는 태스크)
    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

    // 대화 ID로 태스크 조회 (변경)
    const {
        data: tasksData,
        isLoading: isLoadingTasks,
        error: tasksError,
    } = useQuery(
        ["tasks-by-conversation", taskId],
        () => brokerApi.getTasksByConversation(taskId || ""),
        {
            enabled: !!taskId,
            refetchInterval: taskId ? 2000 : false,
        }
    );

    // 첫 번째 태스크를 선택
    useEffect(() => {
        if (tasksData?.tasks?.length > 0) {
            setSelectedTaskId(tasksData.tasks[0].task_id);
        }
    }, [tasksData]);

    // 태스크 결과 조회
    const {
        data: taskDetails,
        isLoading: isLoadingTask,
        error: taskError,
    } = useQuery(
        ["task", selectedTaskId],
        () => brokerApi.getTask(selectedTaskId || ""),
        {
            enabled: !!selectedTaskId,
            refetchInterval: selectedTaskId ? 2000 : false,
        }
    );

    // 새로운 태스크가 선택되면 최근 목록에 추가
    useEffect(() => {
        if (taskId && typeof taskId === "string") {
            setSelectedTaskId(taskId);

            // 태스크 ID가 이미 목록에 있으면 제거하고 맨 앞에 추가
            setRecentTaskIds((prev) => {
                const newIds = [
                    taskId,
                    ...prev.filter((id) => id !== taskId),
                ].slice(0, 10);
                localStorage.setItem("recentTaskIds", JSON.stringify(newIds));
                return newIds;
            });
        }
    }, [taskId]);

    // 태스크 결과 복사
    const copyResult = () => {
        if (taskDetails?.result) {
            const resultText =
                typeof taskDetails.result === "object"
                    ? JSON.stringify(taskDetails.result, null, 2)
                    : String(taskDetails.result);

            navigator.clipboard.writeText(resultText).then(
                () => alert("결과가 클립보드에 복사되었습니다."),
                (err) => alert("복사 중 오류가 발생했습니다: " + err)
            );
        }
    };

    // 태스크 결과 다운로드
    const downloadResult = () => {
        if (taskDetails?.result) {
            const resultText =
                typeof taskDetails.result === "object"
                    ? JSON.stringify(taskDetails.result, null, 2)
                    : String(taskDetails.result);

            const blob = new Blob([resultText], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `ta***REMOVED***result-${taskDetails.task_id}.json`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        }
    };

    // 태스크 결과 표시
    const renderTaskResult = (task: any) => {
        if (!task) return null;

        // 결과가 문자열인 경우
        if (typeof task.result === "string") {
            return <pre className="whitespace-pre-wrap">{task.result}</pre>;
        }

        // 결과가 객체인 경우
        if (typeof task.result === "object") {
            return (
                <pre className="whitespace-pre-wrap">
                    {JSON.stringify(task.result, null, 2)}
                </pre>
            );
        }

        // 결과가 없는 경우
        return <p>결과가 없습니다.</p>;
    };

    // 태스크가 선택되지 않은 경우
    if (!selectedTaskId && !taskId) {
        return (
            <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
                <h2 className="text-xl font-bold mb-4">태스크 결과</h2>

                {recentTaskIds.length > 0 ? (
                    <>
                        <p className="text-gray-500 mb-2">최근 태스크 결과:</p>
                        <ul className="space-y-2">
                            {recentTaskIds.map((id) => (
                                <li key={id}>
                                    <button
                                        onClick={() => setSelectedTaskId(id)}
                                        className="text-blue-600 hover:text-blue-800 text-sm"
                                    >
                                        {/* 이미 문자열임이 보장됨 */}
                                        태스크 {id.slice(0, 8)}...
                                    </button>
                                </li>
                            ))}
                        </ul>
                    </>
                ) : (
                    <p className="text-gray-500">
                        표시할 결과가 없습니다. 새로운 요청을 생성해주세요.
                    </p>
                )}
            </div>
        );
    }

    // 로딩 중인 경우
    if (isLoadingTask) {
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
    if (taskError || !taskDetails) {
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

                {/* 히스토리 드롭다운 */}
                {recentTaskIds.length > 0 && (
                    <div className="relative">
                        <select
                            value={selectedTaskId || taskId || ""}
                            onChange={(e) => setSelectedTaskId(e.target.value)}
                            className="block appearance-none bg-white border border-gray-300 hover:border-gray-400 px-4 py-2 rounded-md shadow-sm text-sm leading-tight focus:outline-none focus:shadow-outline"
                        >
                            {recentTaskIds.map((id) => (
                                <option key={id} value={id}>
                                    {id.substring(0, 8)}...
                                </option>
                            ))}
                        </select>
                        <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-gray-700">
                            <svg
                                className="h-4 w-4"
                                xmlns="http://www.w3.org/2000/svg"
                                viewBox="0 0 20 20"
                                fill="currentColor"
                            >
                                <path
                                    fillRule="evenodd"
                                    d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
                                    clipRule="evenodd"
                                />
                            </svg>
                        </div>
                    </div>
                )}
            </div>

            {/* 태스크 상태 */}
            <div className="mb-4 flex items-center">
                <span
                    className={`inline-block w-3 h-3 rounded-full mr-2 ${
                        taskDetails.status === TaskStatus.COMPLETED
                            ? "bg-green-500"
                            : taskDetails.status === TaskStatus.FAILED
                            ? "bg-red-500"
                            : taskDetails.status === TaskStatus.PROCESSING
                            ? "bg-blue-500"
                            : "bg-gray-500"
                    }`}
                ></span>
                <span className="text-sm text-gray-600">
                    {taskDetails.status === TaskStatus.COMPLETED
                        ? "완료됨"
                        : taskDetails.status === TaskStatus.FAILED
                        ? "실패함"
                        : taskDetails.status === TaskStatus.PROCESSING
                        ? "처리 중"
                        : taskDetails.status === TaskStatus.PENDING
                        ? "대기 중"
                        : "취소됨"}
                </span>

                {/* 복사 및 다운로드 버튼 (결과가 있을 때만) */}
                {taskDetails.result && (
                    <div className="ml-auto space-x-2">
                        <button
                            onClick={copyResult}
                            className="text-sm text-blue-600 hover:text-blue-800"
                            title="결과 복사"
                        >
                            복사
                        </button>
                        <button
                            onClick={downloadResult}
                            className="text-sm text-blue-600 hover:text-blue-800"
                            title="결과 다운로드"
                        >
                            다운로드
                        </button>
                    </div>
                )}
            </div>

            {/* 결과 컨테이너 */}
            <div className="mt-4 border rounded-md overflow-hidden">
                {taskDetails.status === TaskStatus.COMPLETED ? (
                    <div className="max-h-80 overflow-y-auto p-4">
                        {renderTaskResult(taskDetails)}
                    </div>
                ) : taskDetails.status === TaskStatus.FAILED ? (
                    <div className="bg-red-50 p-4 text-red-700">
                        <p className="font-medium">오류 발생:</p>
                        <p className="mt-1">
                            {taskDetails.error ||
                                "알 수 없는 오류가 발생했습니다."}
                        </p>
                    </div>
                ) : (
                    <div className="bg-gray-50 p-8 text-center text-gray-500">
                        <p>태스크 처리 중입니다. 결과가 곧 표시됩니다.</p>
                        <div className="mt-4 flex justify-center">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                        </div>
                    </div>
                )}
            </div>

            {/* 태스크 정보 */}
            <div className="mt-4 text-xs text-gray-500">
                <div className="grid grid-cols-2 gap-2">
                    <div>
                        <span className="font-medium">태스크 ID:</span>{" "}
                        <span className="font-mono">{taskDetails.task_id}</span>
                    </div>
                    <div>
                        <span className="font-medium">역할:</span>{" "}
                        {taskDetails.role}
                    </div>
                    <div>
                        <span className="font-medium">생성 시간:</span>{" "}
                        {new Date(
                            taskDetails.created_at * 1000
                        ).toLocaleString()}
                    </div>
                    {taskDetails.completed_at && (
                        <div>
                            <span className="font-medium">완료 시간:</span>{" "}
                            {new Date(
                                taskDetails.completed_at * 1000
                            ).toLocaleString()}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

// 로컬 스토리지에서 태스크 ID 목록을 가져올 때도 문자열 확인
const getStoredTaskIds = (): string[] => {
    try {
        const stored = localStorage.getItem("recentTaskIds");
        const parsed = stored ? JSON.parse(stored) : [];
        // 문자열인 항목만 필터링
        return Array.isArray(parsed)
            ? parsed.filter((id) => typeof id === "string")
            : [];
    } catch (error) {
        console.error("태스크 ID 목록 로드 중 오류:", error);
        return [];
    }
};

export default ResultViewer;
