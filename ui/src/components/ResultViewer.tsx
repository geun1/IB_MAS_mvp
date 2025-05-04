import React, { useState, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "react-query";
import { orchestratorApi } from "../api/orchestrator";
import ReactMarkdown from "react-markdown";
import { eventEmitter } from "../utils/eventEmitter";

interface ResultViewerProps {
    taskId: string | null;
    className?: string;
}

const ResultViewer: React.FC<ResultViewerProps> = ({
    taskId,
    className = "",
}) => {
    // 마크다운 테이블을 HTML 테이블로 변환한 내용 저장
    const [renderedContent, setRenderedContent] = useState<string>("");
    const [hasResult, setHasResult] = useState<boolean>(false);
    const [isExpanded, setIsExpanded] = useState<boolean>(false); // 결과 확장 상태

    // 폴링 제어 변수
    const lastPollingTime = useRef<number>(0);
    const pollingInterval = 3000; // 3초
    const maxAdditionalPolls = 1;
    const additionalPollsCount = useRef<number>(0);

    // 쿼리 클라이언트
    const queryClient = useQueryClient();

    // 마지막으로 전달한 메시지 추적
    const lastMessageSent = useRef<string | null>(null);

    // 오케스트레이터에서 통합 결과 조회
    const {
        data,
        isLoading,
        isError,
        remove: removeResultQuery,
    } = useQuery(
        ["conversationResult", taskId],
        () => {
            // 현재 시간 체크
            const currentTime = Date.now();

            // 마지막 폴링 이후 충분한 시간이 지났는지 확인
            if (currentTime - lastPollingTime.current < pollingInterval) {
                console.log("ResultViewer - 폴링 간격 유지 중...");
                return Promise.resolve(null);
            }

            // 폴링 시간 업데이트
            lastPollingTime.current = currentTime;

            return taskId
                ? orchestratorApi.getConversationStatus(taskId)
                : null;
        },
        {
            enabled: !!taskId && !hasResult,
            refetchInterval: taskId && !hasResult ? pollingInterval : false,
            onSuccess: (data) => {
                if (!data) return;

                // 작업이 완료되고 결과가 있는 경우 폴링 중지
                if (
                    data.status === "completed" ||
                    data.status === "partially_completed"
                ) {
                    const msg = extractMessage(data);
                    console.log(
                        "ResultViewer - 추출된 메시지:",
                        msg ? msg.substring(0, 50) + "..." : "없음"
                    );

                    if (msg) {
                        // 결과가 있으면 화면에 표시
                        setRenderedContent(convertMarkdownTablesToHtml(msg));

                        // 결과 데이터가 있음을 표시하고 폴링 중지
                        setHasResult(true);
                        console.log("ResultViewer - 결과 있음, 폴링 중지");
                        removeResultQuery();
                        queryClient.removeQueries([
                            "conversationResult",
                            taskId,
                        ]);
                    } else {
                        // 추가 폴링 시도
                        if (additionalPollsCount.current < maxAdditionalPolls) {
                            additionalPollsCount.current++;
                            console.log(
                                `ResultViewer - 완료 후 추가 폴링 (${additionalPollsCount.current}/${maxAdditionalPolls})`
                            );
                        } else {
                            console.log("ResultViewer - 결과 없음, 폴링 중지");
                            setHasResult(true);
                            removeResultQuery();
                            queryClient.removeQueries([
                                "conversationResult",
                                taskId,
                            ]);
                        }
                    }
                }
            },
        }
    );

    // taskId가 변경되면 상태 초기화 - 새 대화 시작
    useEffect(() => {
        if (taskId) {
            lastPollingTime.current = Date.now();
            additionalPollsCount.current = 0;
            setHasResult(false);
            setRenderedContent("");
            setIsExpanded(false); // 새 태스크 시작시 확장 상태 초기화

            // 이미 완료된 대화인 경우 즉시 데이터 가져오기
            if (taskId) {
                orchestratorApi
                    .getConversationStatus(taskId)
                    .then((response) => {
                        if (
                            response &&
                            (response.status === "completed" ||
                                response.status === "partially_completed")
                        ) {
                            const msg = extractMessage(response);
                            if (msg) {
                                setRenderedContent(
                                    convertMarkdownTablesToHtml(msg)
                                );
                                setHasResult(true);
                            }
                        }
                    })
                    .catch((err) =>
                        console.error("이전 대화 데이터 로딩 오류:", err)
                    );
            }
        }
    }, [taskId]);

    // 중첩된 결과 구조에서 메시지 추출
    const extractMessage = (data: any): string => {
        if (!data) return "";

        console.log("결과 추출 시도:", data); // 디버깅용 로깅

        // 직접 'message' 필드가 있는 경우
        if (data.message && typeof data.message === "string") {
            console.log("최상위 message 필드 감지");
            return data.message;
        }

        // 결과가 이미 포맷팅된 문자열인 경우
        if (typeof data === "string") {
            console.log("결과가 직접 문자열");
            return data;
        }

        // 중첩 구조: result > data - stock_data_agent용
        if (data.result && data.result.data) {
            console.log("stock_data_agent 구조 감지: result.data");
            try {
                return `주식 데이터 결과:\n\`\`\`json\n${JSON.stringify(
                    data.result.data,
                    null,
                    2
                )}\n\`\`\``;
            } catch (e) {
                console.error("JSON 변환 오류:", e);
            }
        }

        // 중첩 구조: result > result > content
        if (data.result && typeof data.result === "object") {
            if (
                data.result.result &&
                typeof data.result.result === "object" &&
                data.result.result.content
            ) {
                console.log("result.result.content 구조 감지");
                return String(data.result.result.content);
            }

            // 중첩 구조: result > result > message
            if (
                data.result.result &&
                typeof data.result.result === "object" &&
                data.result.result.message
            ) {
                console.log("result.result.message 구조 감지");
                return String(data.result.result.message);
            }

            // 단일 수준 구조: result > message
            if (data.result.message) {
                console.log("result.message 구조 감지");
                return String(data.result.message);
            }

            // 단일 수준 구조: result > content
            if (data.result.content) {
                console.log("result.content 구조 감지");
                return String(data.result.content);
            }

            // 직접 result 개체인 경우
            if (typeof data.result === "string") {
                console.log("result가 직접 문자열");
                return data.result;
            }
        }

        // tasks 배열이 있고 완료된 태스크가 있는 경우
        if (data.tasks && Array.isArray(data.tasks) && data.tasks.length > 0) {
            console.log("tasks 배열 감지");

            const completedTasks = data.tasks.filter(
                (task: any) => task.status === "completed"
            );

            if (completedTasks.length > 0) {
                // 가장 마지막 완료된 태스크 사용
                const lastTask = completedTasks[completedTasks.length - 1];

                if (lastTask.result) {
                    // stock_data_agent 결과 구조 처리
                    if (lastTask.result.data) {
                        console.log(
                            "stock_data_agent 구조 감지: task.result.data"
                        );
                        try {
                            return `주식 데이터 결과:\n\`\`\`json\n${JSON.stringify(
                                lastTask.result.data,
                                null,
                                2
                            )}\n\`\`\``;
                        } catch (e) {
                            console.error("JSON 변환 오류:", e);
                        }
                    }

                    // 태스크 결과에서 중첩 구조 확인
                    if (
                        lastTask.result.result &&
                        lastTask.result.result.content
                    ) {
                        console.log("task.result.result.content 구조 감지");
                        return String(lastTask.result.result.content);
                    }

                    if (
                        lastTask.result.result &&
                        lastTask.result.result.message
                    ) {
                        console.log("task.result.result.message 구조 감지");
                        return String(lastTask.result.result.message);
                    }

                    if (lastTask.result.content) {
                        console.log("task.result.content 구조 감지");
                        return String(lastTask.result.content);
                    }

                    if (lastTask.result.message) {
                        console.log("task.result.message 구조 감지");
                        return String(lastTask.result.message);
                    }

                    if (typeof lastTask.result === "string") {
                        console.log("task.result가 직접 문자열");
                        return lastTask.result;
                    }
                }
            }
        }

        // 결과가 있지만 예상 구조가 아닌 경우 JSON으로 변환
        if (data.result) {
            try {
                const resultJson = JSON.stringify(data.result, null, 2);
                console.log(
                    "결과를 JSON으로 변환:",
                    resultJson.slice(0, 100) + "..."
                );
                return `\`\`\`json\n${resultJson}\n\`\`\``;
            } catch (e) {
                console.error("JSON 변환 오류:", e);
            }
        }

        // 아무것도 찾지 못한 경우 원본 데이터 리턴
        try {
            const dataJson = JSON.stringify(data, null, 2);
            console.log(
                "모든 데이터를 JSON으로 변환:",
                dataJson.slice(0, 100) + "..."
            );
            return `\`\`\`json\n${dataJson}\n\`\`\``;
        } catch (e) {
            console.error("JSON 변환 오류:", e);
        }

        return "결과를 표시할 수 없습니다.";
    };

    // 마크다운 테이블을 HTML로 변환
    const convertMarkdownTablesToHtml = (content: string): string => {
        if (!content) return "";

        // 테이블 처리
        const tableRegex =
            /\|(.+)\|[\r\n]+\|([\s-:|]+)\|[\r\n]+((?:\|.+\|[\r\n]+)+)/g;

        return content.replace(
            tableRegex,
            (
                match: string,
                headerRow: string,
                separatorRow: string,
                bodyRows: string
            ) => {
                try {
                    // 헤더 처리
                    const headers = headerRow
                        .split("|")
                        .map((cell: string) => cell.trim())
                        .filter((cell: string) => cell);

                    // 구분자 처리 (정렬 정보 포함)
                    const alignments = separatorRow
                        .split("|")
                        .map((sep: string) => sep.trim())
                        .filter((sep: string) => sep)
                        .map((sep: string) => {
                            if (sep.startsWith(":") && sep.endsWith(":"))
                                return "center";
                            if (sep.endsWith(":")) return "right";
                            return "left";
                        });

                    // 바디 처리
                    const rows = bodyRows
                        .trim()
                        .split("\n")
                        .map((row: string) =>
                            row
                                .split("|")
                                .map((cell: string) => cell.trim())
                                .filter((cell: string) => cell !== "")
                        );

                    // HTML 테이블 생성
                    let htmlTable = `<div class="overflow-x-auto">
                        <table class="min-w-full divide-y divide-gray-200">
                            <thead class="bg-gray-50">
                                <tr>`;

                    // 헤더 셀 추가
                    headers.forEach((header: string, index: number) => {
                        const alignment =
                            index < alignments.length
                                ? alignments[index]
                                : "left";
                        htmlTable += `<th scope="col" class="px-6 py-3 text-${alignment} text-xs font-medium text-gray-500 uppercase tracking-wider">${header}</th>`;
                    });

                    htmlTable += `</tr>
                            </thead>
                            <tbody class="bg-white divide-y divide-gray-200">`;

                    // 행 추가
                    rows.forEach((row: string[], rowIndex: number) => {
                        htmlTable += `<tr class="${
                            rowIndex % 2 === 0 ? "bg-white" : "bg-gray-50"
                        }">`;
                        row.forEach((cell: string, cellIndex: number) => {
                            const alignment =
                                cellIndex < alignments.length
                                    ? alignments[cellIndex]
                                    : "left";
                            htmlTable += `<td class="px-6 py-4 whitespace-normal text-${alignment} text-sm text-gray-500">${cell}</td>`;
                        });
                        htmlTable += "</tr>";
                    });

                    htmlTable += `</tbody>
                        </table>
                    </div>`;

                    return htmlTable;
                } catch (error) {
                    console.error("테이블 변환 오류:", error);
                    return match; // 오류 발생 시 원본 반환
                }
            }
        );
    };

    const content = data ? extractMessage(data) : "";

    useEffect(() => {
        if (content && content !== lastMessageSent.current) {
            setRenderedContent(convertMarkdownTablesToHtml(content));
            lastMessageSent.current = content;
        }
    }, [content]);

    // 결과 확장/축소 토글
    const toggleExpansion = () => {
        setIsExpanded(!isExpanded);
    };

    if (isLoading && !renderedContent) {
        return (
            <div
                className={`${className} p-4 bg-white rounded-lg shadow-md text-center`}
            >
                <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full inline-block"></div>
                <p className="mt-2 text-gray-600">결과를 가져오는 중...</p>
            </div>
        );
    }

    if (isError && !renderedContent) {
        return (
            <div
                className={`${className} p-4 bg-white rounded-lg shadow-md text-center text-red-500`}
            >
                결과를 가져오는 중 오류가 발생했습니다.
            </div>
        );
    }

    if (!renderedContent) {
        return (
            <div
                className={`${className} p-4 bg-white rounded-lg shadow-md text-center text-gray-500`}
            >
                아직 결과가 없습니다.
            </div>
        );
    }

    return (
        <div className={`${className} bg-white rounded-lg shadow-md`}>
            <div
                className="px-4 py-3 border-b flex items-center justify-between cursor-pointer hover:bg-gray-50"
                onClick={toggleExpansion}
            >
                <h3 className="text-lg font-medium">에이전트 최종 응답</h3>
                <svg
                    className={`w-5 h-5 transition-transform ${
                        isExpanded ? "transform rotate-180" : ""
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
            {isExpanded && (
                <div className="p-4">
                    {renderedContent.includes("<table") ? (
                        <div
                            dangerouslySetInnerHTML={{
                                __html: renderedContent,
                            }}
                        />
                    ) : (
                        <div className="prose max-w-none">
                            <ReactMarkdown>{content}</ReactMarkdown>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default ResultViewer;
