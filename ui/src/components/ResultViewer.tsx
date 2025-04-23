import React, { useState } from "react";
import { useQuery } from "react-query";
import { brokerApi } from "../api/broker";
import { TaskResult, TaskStatus } from "../types";

const ResultViewer: React.FC = () => {
    const [page, setPage] = useState(1);
    const pageSize = 3; // 페이지당 태스크 수

    // 전체 태스크 목록 조회
    const { data, isLoading, isError } = useQuery(
        ["taskResults", page],
        () => brokerApi.listTasks(page, pageSize),
        {
            refetchInterval: 10000, // 10초마다 갱신
        }
    );

    // 로딩 중 표시
    if (isLoading) {
        return (
            <div className="bg-white rounded-lg shadow-md p-4">
                <div className="flex items-center justify-center">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
                    <span className="ml-2">결과 로딩 중...</span>
                </div>
            </div>
        );
    }

    // 에러 표시
    if (isError) {
        return (
            <div className="bg-white rounded-lg shadow-md p-4">
                <div className="text-red-600">
                    결과를 가져오는 중 오류가 발생했습니다.
                </div>
            </div>
        );
    }

    // 결과가 없는 경우
    if (!data || data.tasks.length === 0) {
        return (
            <div className="bg-white rounded-lg shadow-md p-4">
                <div className="text-gray-600">태스크 결과가 없습니다.</div>
            </div>
        );
    }

    // 결과 표시
    return (
        <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-lg font-semibold mb-4">태스크 결과 목록</h3>
            <div className="space-y-4">
                {data.tasks.map((task: TaskResult) => (
                    <TaskItem key={task.task_id} task={task} />
                ))}
            </div>
            <div className="flex justify-between mt-4">
                <button
                    onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
                    disabled={page === 1}
                    className="px-4 py-2 bg-gray-300 rounded disabled:opacity-50"
                >
                    이전
                </button>
                <span>페이지 {page}</span>
                <button
                    onClick={() => setPage((prev) => prev + 1)}
                    disabled={data.tasks.length < pageSize}
                    className="px-4 py-2 bg-gray-300 rounded disabled:opacity-50"
                >
                    다음
                </button>
            </div>
        </div>
    );
};

const TaskItem: React.FC<{ task: TaskResult }> = ({ task }) => {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <div className="border-b pb-4 mb-4">
            <div>
                <span className="font-medium">태스크 ID:</span> {task.task_id}
            </div>
            <div>
                <span className="font-medium">상태:</span>{" "}
                <span
                    className={`px-2 py-1 rounded-full text-sm ${getStatusStyle(
                        task.status
                    )}`}
                >
                    {getStatusText(task.status)}
                </span>
            </div>
            <div>
                <span className="font-medium">역할:</span> {task.role}
            </div>
            <div>
                <button
                    onClick={() => setIsOpen(!isOpen)}
                    className="text-blue-500 underline"
                >
                    {isOpen ? "결과 닫기" : "결과 보기"}
                </button>
                {isOpen && (
                    <div className="mt-2">
                        <span className="font-medium">결과:</span>{" "}
                        {task.result?.result?.content || "결과 없음"}
                    </div>
                )}
            </div>
            <div>
                <span className="font-medium">생성 시간:</span>{" "}
                {new Date(task.created_at * 1000).toLocaleString()}
            </div>
            <div>
                <span className="font-medium">업데이트 시간:</span>{" "}
                {new Date(task.updated_at * 1000).toLocaleString()}
            </div>
            {task.completed_at && (
                <div>
                    <span className="font-medium">완료 시간:</span>{" "}
                    {new Date(task.completed_at * 1000).toLocaleString()}
                </div>
            )}
            {task.error && (
                <div className="text-red-600">
                    <span className="font-medium">오류:</span> {task.error}
                </div>
            )}
        </div>
    );
};

// 상태에 따른 스타일
const getStatusStyle = (status: string) => {
    switch (status) {
        case TaskStatus.COMPLETED:
            return "bg-green-100 text-green-800";
        case TaskStatus.PROCESSING:
            return "bg-blue-100 text-blue-800";
        case TaskStatus.PENDING:
            return "bg-yellow-100 text-yellow-800";
        case TaskStatus.FAILED:
            return "bg-red-100 text-red-800";
        default:
            return "bg-gray-100 text-gray-800";
    }
};

// 상태 텍스트
const getStatusText = (status: string) => {
    switch (status) {
        case TaskStatus.COMPLETED:
            return "완료";
        case TaskStatus.PROCESSING:
            return "처리 중";
        case TaskStatus.PENDING:
            return "대기 중";
        case TaskStatus.FAILED:
            return "실패";
        default:
            return "알 수 없음";
    }
};

export default ResultViewer;
