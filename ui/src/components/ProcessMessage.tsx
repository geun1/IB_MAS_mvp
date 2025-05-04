import React, { useState } from "react";
import ReactMarkdown from "react-markdown";

interface ProcessMessageProps {
    type: "task_split" | "agent_processing" | "agent_result";
    role?: string;
    content: string;
    timestamp: Date;
    className?: string;
    taskIndex?: number;
    taskDescription?: string;
}

/**
 * 처리 과정 메시지 컴포넌트
 * 작업 분할, 에이전트 처리, 에이전트 결과 등 처리 상태를 보여줌
 */
const ProcessMessage: React.FC<ProcessMessageProps> = ({
    type,
    role,
    content,
    timestamp,
    className = "",
    taskIndex,
    taskDescription,
}) => {
    // 기본적으로 모든 메시지 타입이 접힌 상태로 시작하도록 수정
    const [expanded, setExpanded] = useState(false);

    // 메시지 타입에 따라 스타일 결정
    const getBgColor = () => {
        switch (type) {
            case "task_split":
                return "bg-gray-100";
            case "agent_processing":
                return "bg-yellow-50";
            case "agent_result":
                return "bg-green-50";
            default:
                return "bg-gray-100";
        }
    };

    // 아이콘 결정
    const getIcon = () => {
        switch (type) {
            case "task_split":
                return (
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-5 w-5 text-gray-600"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                    >
                        <path
                            fillRule="evenodd"
                            d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z"
                            clipRule="evenodd"
                        />
                    </svg>
                );
            case "agent_processing":
                return (
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-5 w-5 text-yellow-600"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                    >
                        <path
                            fillRule="evenodd"
                            d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
                            clipRule="evenodd"
                        />
                    </svg>
                );
            case "agent_result":
                return (
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-5 w-5 text-green-600"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                    >
                        <path
                            fillRule="evenodd"
                            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                            clipRule="evenodd"
                        />
                    </svg>
                );
        }
    };

    // 헤더 텍스트 결정
    const getHeaderText = () => {
        switch (type) {
            case "task_split":
                return "태스크 분리";
            case "agent_processing":
                return role ? `${role} 처리 중...` : "처리 중...";
            case "agent_result":
                return role ? `${role} 결과` : "처리 결과";
        }
    };

    // 태스크 정보 표시
    const renderTaskInfo = () => {
        if (taskIndex !== undefined && taskDescription) {
            return (
                <div className="text-xs text-gray-600 mt-1">
                    <span className="font-semibold">
                        태스크 {taskIndex + 1}
                    </span>
                    : {taskDescription}
                </div>
            );
        }
        return null;
    };

    return (
        <div
            className={`rounded-lg p-3 mr-auto w-full ${getBgColor()} ${className} mb-2`}
        >
            <div className="flex justify-between items-start">
                <div className="flex items-center space-x-2">
                    {getIcon()}
                    <span className="font-medium">{getHeaderText()}</span>
                    <span className="text-xs text-gray-500">
                        {timestamp.toLocaleTimeString()}
                    </span>
                </div>
                {/* 모든 메시지 타입에 드롭다운 버튼 추가 */}
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="text-gray-500 hover:text-gray-700"
                >
                    {expanded ? (
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            className="h-5 w-5"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                        >
                            <path
                                fillRule="evenodd"
                                d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z"
                                clipRule="evenodd"
                            />
                        </svg>
                    ) : (
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            className="h-5 w-5"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                        >
                            <path
                                fillRule="evenodd"
                                d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
                                clipRule="evenodd"
                            />
                        </svg>
                    )}
                </button>
            </div>

            {renderTaskInfo()}

            {expanded && (
                <div className="mt-2 max-w-full overflow-x-auto prose prose-sm">
                    <ReactMarkdown>{content}</ReactMarkdown>
                </div>
            )}
        </div>
    );
};

export default ProcessMessage;
