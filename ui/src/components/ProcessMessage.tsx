import React, { useState } from "react";
import ReactMarkdown from "react-markdown";

// ProcessMessage 타입 정의
export type ProcessMessageType =
    | "task_split"
    | "agent_processing"
    | "agent_result"
    | "react_agent";

export interface ProcessMessage {
    type: ProcessMessageType;
    role: string;
    content: string;
    timestamp: Date;
    messageId?: string;
    taskDescription?: string;
    taskIndex?: number;
    status?: string;
    stepInfo?: {
        total: number;
        reasoning: number;
        action: number;
        observation: number;
    };
}

// 컴포넌트 인터페이스
interface ProcessMessageProps {
    type: ProcessMessageType;
    role: string;
    content: string;
    timestamp: Date;
    messageId?: string;
    taskDescription?: string;
    taskIndex?: number;
    status?: string;
    stepInfo?: {
        total: number;
        reasoning: number;
        action: number;
        observation: number;
    };
}

// 마크다운 테이블을 HTML로 변환
const convertMarkdownTablesToHtml = (content: string): string => {
    if (!content) return content;

    // 테이블 처리
    const tableRegex =
        /\|(.+)\|[\r\n]+\|([\s-:|]+)\|[\r\n]+((?:\|.+\|[\r\n]+)+)/g;

    return content.replace(
        tableRegex,
        (match, headerRow, separatorRow, bodyRows) => {
            try {
                // 헤더 처리
                const headers = headerRow
                    .split("|")
                    .map((cell: string) => cell.trim())
                    .filter(Boolean);

                // 본문 처리
                const rows = bodyRows.trim().split("\n");

                // HTML 테이블 생성
                let htmlTable =
                    '<div class="overflow-x-auto my-4 rounded-lg border border-gray-300 shadow">';
                htmlTable +=
                    '<table class="min-w-full border-collapse table-fixed">';

                // 헤더 추가
                htmlTable += '<thead class="bg-gray-100"><tr>';
                headers.forEach((header: string) => {
                    htmlTable += `<th class="border-b border-r last:border-r-0 border-gray-300 px-4 py-3 text-left font-semibold text-gray-700 text-sm">${header}</th>`;
                });
                htmlTable += "</tr></thead>";

                // 본문 추가
                htmlTable += '<tbody class="divide-y divide-gray-200">';
                rows.forEach((row: string) => {
                    if (row.trim()) {
                        const cells = row
                            .split("|")
                            .map((cell: string) => cell.trim())
                            .filter(Boolean);
                        htmlTable += '<tr class="hover:bg-gray-50">';
                        cells.forEach((cell: string) => {
                            // <br> 태그를 실제 줄바꿈으로 변환
                            const processedCell = cell.replace(
                                /<br>/g,
                                "<br/>"
                            );
                            htmlTable += `<td class="border-b border-r last:border-r-0 border-gray-300 px-4 py-3 text-gray-800 text-sm align-middle whitespace-pre-line">${processedCell}</td>`;
                        });
                        htmlTable += "</tr>";
                    }
                });
                htmlTable += "</tbody></table></div>";

                return htmlTable;
            } catch (e) {
                console.error("테이블 변환 오류:", e);
                return match; // 오류 발생 시 원본 반환
            }
        }
    );
};

/**
 * 처리 과정 메시지 컴포넌트
 * 작업 분할, 에이전트 처리, 에이전트 결과 등 처리 상태를 보여줌
 */
const ProcessMessage: React.FC<ProcessMessageProps> = ({
    type,
    role,
    content,
    timestamp,
    messageId,
    taskDescription,
    taskIndex,
    status,
    stepInfo,
}) => {
    // 모든 메시지 타입에 대해 기본 상태를 접힌 상태로 설정
    const [expanded, setExpanded] = useState(false);

    // 메시지 타입에 따라 스타일 결정
    const getBgColor = () => {
        // 태스크 결과인 경우 상태에 따라 다른 스타일 적용
        if (type === "agent_result" && status) {
            switch (status) {
                case "completed":
                    return "bg-green-50 border border-green-200";
                case "processing":
                    return "bg-yellow-50 border border-yellow-200";
                case "failed":
                    return "bg-red-50 border border-red-200";
                default:
                    return "bg-gray-50 border border-gray-200";
            }
        }

        switch (type) {
            case "task_split":
                return "bg-purple-50 border-purple-200";
            case "agent_processing":
                return "bg-yellow-50 border border-yellow-200";
            case "agent_result":
                return "bg-blue-50 border-blue-200";
            case "react_agent":
                return "bg-green-50 border-green-200";
            default:
                return "bg-gray-50 border border-gray-200";
        }
    };

    // 아이콘 결정
    const getIcon = () => {
        // 태스크 결과인 경우 상태에 따라 다른 아이콘 적용
        if (type === "agent_result" && status) {
            switch (status) {
                case "completed":
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
                case "processing":
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
                case "failed":
                    return (
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            className="h-5 w-5 text-red-600"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                        >
                            <path
                                fillRule="evenodd"
                                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                                clipRule="evenodd"
                            />
                        </svg>
                    );
                default:
                    return (
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            className="h-5 w-5 text-gray-600"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                        >
                            <path
                                fillRule="evenodd"
                                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z"
                                clipRule="evenodd"
                            />
                        </svg>
                    );
            }
        }

        // 기존 로직 유지
        switch (type) {
            case "task_split":
                return (
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-5 w-5 text-purple-600"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                    >
                        <path d="M5 3a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2v-2a2 2 0 00-2-2H5zM11 5a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V5zM11 13a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
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
                        className="h-5 w-5 text-blue-600"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                    >
                        <path
                            fillRule="evenodd"
                            d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z"
                            clipRule="evenodd"
                        />
                    </svg>
                );
            case "react_agent":
                return (
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-5 w-5 text-green-600"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                    >
                        <path
                            fillRule="evenodd"
                            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                            clipRule="evenodd"
                        />
                    </svg>
                );
        }
    };

    // 헤더 텍스트 결정
    const getHeaderText = () => {
        // 태스크 결과인 경우 상태 표시 추가
        if (type === "agent_result" && status) {
            const statusText =
                status === "completed"
                    ? "완료"
                    : status === "processing"
                    ? "처리 중"
                    : status === "failed"
                    ? "실패"
                    : status;

            return role
                ? `${role} 결과 (${statusText})`
                : `처리 결과 (${statusText})`;
        }

        switch (type) {
            case "task_split":
                return "태스크 분리";
            case "agent_processing":
                return role ? `${role} 처리 중...` : "처리 중...";
            case "agent_result":
                return role ? `${role} 결과` : "처리 결과";
            case "react_agent":
                return taskDescription || "여행 계획 ReAct 에이전트";
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

    // 콘텐츠 출력 - 확장 상태일 때만 내용 표시
    const renderContent = () => {
        if (!content.trim() || !expanded) return null;

        // 확장 상태일 때만 내용 표시
        return (
            <div className="mt-2 max-w-full overflow-x-auto prose prose-sm max-h-80 overflow-y-auto">
                <ReactMarkdown>{content}</ReactMarkdown>
            </div>
        );
    };

    // ReAct 단계 타임라인 렌더링 함수 추가
    const renderReactTimeline = () => {
        if (type !== "react_agent" || !stepInfo) return null;

        // 단계 진행 데이터 준비
        const steps = [];
        let currentStep = 0;

        // 각 단계별 진행 과정을 표시
        for (let i = 0; i < stepInfo.total; i++) {
            // 현재 단계에 따라 단계별 타입 결정 (추론 → 행동 → 관찰 순환)
            let stepType = "";
            let color = "";

            if (currentStep === 0) {
                stepType = "추론";
                color = "bg-yellow-400";
            } else if (currentStep === 1) {
                stepType = "행동";
                color = "bg-blue-400";
            } else {
                stepType = "관찰";
                color = "bg-purple-400";
            }

            steps.push({ type: stepType, color });

            // 다음 단계로 순환 (0→1→2→0→...)
            currentStep = (currentStep + 1) % 3;
        }

        return (
            <div className="mt-3 pt-3 border-t border-gray-200">
                <h4 className="text-sm font-semibold mb-2">ReAct 진행 과정</h4>
                <div className="flex flex-wrap items-center gap-1 mb-2">
                    {steps.map((step, idx) => (
                        <div key={idx} className="flex flex-col items-center">
                            <div
                                className={`w-7 h-7 rounded-full ${step.color} flex items-center justify-center shadow-sm text-white text-xs font-medium`}
                            >
                                {idx + 1}
                            </div>
                            <span className="text-xs mt-1">{step.type}</span>
                        </div>
                    ))}
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className="bg-yellow-100 text-yellow-800 p-2 rounded-md flex flex-col items-center">
                        <span className="font-semibold">추론</span>
                        <span>{stepInfo.reasoning}회</span>
                    </div>
                    <div className="bg-blue-100 text-blue-800 p-2 rounded-md flex flex-col items-center">
                        <span className="font-semibold">행동</span>
                        <span>{stepInfo.action}회</span>
                    </div>
                    <div className="bg-purple-100 text-purple-800 p-2 rounded-md flex flex-col items-center">
                        <span className="font-semibold">관찰</span>
                        <span>{stepInfo.observation}회</span>
                    </div>
                </div>
            </div>
        );
    };

    // 태스크 번호와 상태에 따른 배지
    let statusBadge = null;

    if (status) {
        const statusClass =
            status === "completed"
                ? "bg-green-100 text-green-800"
                : status === "running"
                ? "bg-blue-100 text-blue-800"
                : "bg-gray-100 text-gray-800";

        statusBadge = (
            <span
                className={`px-2 py-0.5 text-xs rounded-full ${statusClass} ml-2`}
            >
                {status === "completed"
                    ? "완료"
                    : status === "running"
                    ? "진행중"
                    : "대기중"}
            </span>
        );
    }

    // 태스크 인덱스 표시
    let indexBadge = null;
    if (typeof taskIndex === "number") {
        indexBadge = (
            <span className="px-2 py-0.5 text-xs rounded-full bg-gray-200 text-gray-700 ml-2">
                #{taskIndex + 1}
            </span>
        );
    }

    // ReAct 에이전트의 경우 단계 정보 표시
    let reactStepInfo = null;
    if (type === "react_agent" && stepInfo) {
        reactStepInfo = (
            <div className="mt-2 flex space-x-2 text-xs">
                <span className="px-2 py-1 rounded bg-green-100 text-green-800">
                    총 단계: {stepInfo.total}회
                </span>
            </div>
        );
    }

    // HTML 로 변환된 콘텐츠
    const processedContent = convertMarkdownTablesToHtml(content);

    return (
        <div
            className={`rounded-lg p-3 mr-auto w-full shadow-sm ${getBgColor()} mb-2`}
        >
            <div className="flex justify-between items-start">
                <div className="flex items-center space-x-2">
                    {getIcon()}
                    <span className="font-medium">{getHeaderText()}</span>
                    {indexBadge}
                    {statusBadge}
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
            {reactStepInfo}
            {renderReactTimeline()}
            {renderContent()}
        </div>
    );
};

export default ProcessMessage;
