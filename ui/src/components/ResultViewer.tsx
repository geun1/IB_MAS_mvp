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
                    if (msg) {
                        // 최대 1번의 추가 폴링 허용 (누락된 결과 확인용)
                        if (additionalPollsCount.current < maxAdditionalPolls) {
                            additionalPollsCount.current++;
                            console.log(
                                `ResultViewer - 완료 후 추가 폴링 (${additionalPollsCount.current}/${maxAdditionalPolls})`
                            );
                        } else {
                            console.log("ResultViewer - 결과 있음, 폴링 중지");
                            setHasResult(true);
                            removeResultQuery();

                            // 캐시에서도 제거
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

    // 컴포넌트 마운트 시 폴링 시간 초기화
    useEffect(() => {
        if (taskId) {
            lastPollingTime.current = Date.now();
            additionalPollsCount.current = 0;
            setHasResult(false);
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

    // 추출된 메시지
    const message = extractMessage(data);

    // 메시지가 변경될 때마다 HTML 변환 및 이벤트 발행
    useEffect(() => {
        if (message) {
            const html = convertMarkdownTablesToHtml(message);
            setRenderedContent(html);

            // 처음 결과가 로드되거나 새로운 결과가 있을 때 이벤트 발행
            if (message !== lastMessageSent.current) {
                console.log(
                    "최종 결과 이벤트 발행:",
                    message.substring(0, 50) + "..."
                );
                eventEmitter.emit("finalResult", {
                    content: message,
                    timestamp: new Date(),
                    conversationId: taskId,
                });
                lastMessageSent.current = message;
            }
        } else {
            setRenderedContent("");
        }
    }, [message, taskId]);

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

    // 오류 발생 시
    if (isError) {
        return (
            <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
                <h3 className="text-lg font-semibold mb-4">결과</h3>
                <div className="text-red-500 p-4">
                    결과를 불러오는 중 오류가 발생했습니다.
                </div>
            </div>
        );
    }

    // 결과가 없는 경우
    if (!message) {
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

    // 결과 표시 (HTML 직접 렌더링)
    return (
        <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
            <h3 className="text-lg font-semibold mb-4">결과</h3>
            <div className="prose prose-sm sm:prose lg:prose-lg max-w-none">
                <div dangerouslySetInnerHTML={{ __html: renderedContent }} />
            </div>
        </div>
    );
};

export default ResultViewer;
