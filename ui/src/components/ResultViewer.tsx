import React, { useState } from "react";
import { useQuery } from "react-query";
import { orchestratorApi } from "../api/orchestrator";
import ReactMarkdown from "react-markdown";

interface ResultViewerProps {
    taskId: string | null;
    className?: string;
}

const ResultViewer: React.FC<ResultViewerProps> = ({
    taskId,
    className = "",
}) => {
    // 오케스트레이터에서 통합 결과 조회
    const { data, isLoading, isError } = useQuery(
        ["conversationResult", taskId],
        () => orchestratorApi.getConversationStatus(taskId || ""),
        {
            enabled: !!taskId,
            refetchInterval: taskId ? 3000 : false, // 3초마다 갱신
        }
    );

    // 로딩 중 표시
    if (isLoading) {
        return (
            <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
                <h3 className="text-lg font-semibold mb-4">결과</h3>
                <div className="flex items-center justify-center p-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    <span className="ml-2">결과 로딩 중...</span>
                </div>
            </div>
        );
    }

    // 에러 표시
    if (isError) {
        return (
            <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
                <h3 className="text-lg font-semibold mb-4">결과</h3>
                <div className="bg-red-50 text-red-600 p-4 rounded-md">
                    결과를 가져오는 중 오류가 발생했습니다.
                </div>
            </div>
        );
    }

    // 결과가 없는 경우
    if (!data || !data.message) {
        return (
            <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
                <h3 className="text-lg font-semibold mb-4">결과</h3>
                <div className="text-gray-500 p-4">
                    {data?.status === "processing"
                        ? "태스크가 처리 중입니다. 잠시 기다려 주세요..."
                        : "아직 결과가 없습니다."}
                </div>
            </div>
        );
    }

    // 결과 표시
    return (
        <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
            <h3 className="text-lg font-semibold mb-4">결과</h3>
            <div className="prose max-w-none">
                <ReactMarkdown>{data.message}</ReactMarkdown>
            </div>
        </div>
    );
};

export default ResultViewer;
