import React, { useState, useEffect } from "react";
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
    // 마크다운 테이블을 HTML 테이블로 변환한 내용 저장
    const [renderedContent, setRenderedContent] = useState<string>("");

    // 오케스트레이터에서 통합 결과 조회
    const { data, isLoading, isError } = useQuery(
        ["conversationResult", taskId],
        () => orchestratorApi.getConversationStatus(taskId || ""),
        {
            enabled: !!taskId,
            refetchInterval: taskId ? 3000 : false, // 3초마다 갱신
        }
    );

    // 중첩된 결과 구조에서 메시지 추출
    const extractMessage = (data: any): string => {
        if (!data) return "";

        // 결과가 중첩된 구조인 경우 (result.result.message)
        if (
            data.result &&
            typeof data.result === "object" &&
            data.result.result
        ) {
            return data.result.result.message || "";
        }

        // 단일 수준 구조인 경우 (result.message)
        if (data.result && typeof data.result === "object") {
            return data.result.message || "";
        }

        // 직접 message 필드가 있는 경우
        return data.message || "";
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

    // 메시지가 변경될 때마다 HTML 변환
    useEffect(() => {
        if (message) {
            const html = convertMarkdownTablesToHtml(message);
            setRenderedContent(html);
        } else {
            setRenderedContent("");
        }
    }, [message]);

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
