import React, { useState, useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "react-query";
import { orchestratorApi } from "../api/orchestrator";
import { QueryRequest } from "../types";
import { agentConfigService } from "../services/AgentConfigService";
import ReactMarkdown from "react-markdown";
import ProcessMessage from "./ProcessMessage";
import {
    Message,
    ProcessMessage as ProcessMessageType,
    TaskInfo,
    ConversationStatus,
} from "../types/messages";
import { eventEmitter } from "../utils/eventEmitter";

interface RequestFormProps {
    onTaskCreated: (taskId: string) => void;
}

// 태스크 그룹화 인터페이스
interface TaskGroup {
    index: number;
    description: string;
    role: string;
    tasks: TaskInfo[];
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

// 결과에서 메시지 추출
const extractMessage = (data: any): string => {
    if (!data) return "";

    console.log("응답 데이터 분석:", data); // 디버깅용 로깅

    // 결과가 이미 문자열인 경우
    if (typeof data === "string") {
        console.log("결과가 직접 문자열");
        return data;
    }

    // 직접 'message' 필드가 있고 내용이 있는 경우
    if (
        data.message &&
        data.message.trim() !== "처리가 완료되었으나 결과가 없습니다."
    ) {
        console.log("최상위 message 필드 감지");
        return String(data.message);
    }

    // tasks 배열이 있는 경우
    if (data.tasks && Array.isArray(data.tasks) && data.tasks.length > 0) {
        console.log("tasks 배열 감지");

        // 완료된 태스크 중에서 찾기
        const completedTasks = data.tasks.filter(
            (task: any) => task.status === "completed"
        );
        if (completedTasks.length > 0) {
            // 가장 마지막 완료된 태스크 사용
            const lastTask = completedTasks[completedTasks.length - 1];

            // 중첩된 결과 구조 확인
            if (lastTask.result) {
                // 구조: result > result > content
                if (lastTask.result.result && lastTask.result.result.content) {
                    console.log("task.result.result.content 구조 감지");
                    return String(lastTask.result.result.content);
                }

                // 구조: result > message
                if (lastTask.result.message) {
                    console.log("task.result.message 구조 감지");
                    return String(lastTask.result.message);
                }

                // 구조: result > content
                if (lastTask.result.content) {
                    console.log("task.result.content 구조 감지");
                    return String(lastTask.result.content);
                }

                // 구조: result > result > message
                if (lastTask.result.result && lastTask.result.result.message) {
                    console.log("task.result.result.message 구조 감지");
                    return String(lastTask.result.result.message);
                }

                // 구조: result가 직접 문자열인 경우
                if (typeof lastTask.result === "string") {
                    console.log("task.result가 직접 문자열");
                    return lastTask.result;
                }

                // 구조: result가 객체이지만 다른 형태인 경우 JSON으로 반환
                if (typeof lastTask.result === "object") {
                    try {
                        console.log("task.result가 객체, JSON으로 변환");
                        return JSON.stringify(lastTask.result, null, 2);
                    } catch (e) {
                        console.error("JSON 변환 오류:", e);
                    }
                }
            }
        }
    }

    // 결과가 중첩된 구조인 경우 (result.result.message/content)
    if (data.result && typeof data.result === "object" && data.result.result) {
        console.log("result.result 구조 감지");
        if (data.result.result.content) {
            console.log("result.result.content 감지");
            return String(data.result.result.content);
        }
        if (data.result.result.message) {
            console.log("result.result.message 감지");
            return String(data.result.result.message);
        }
        return "";
    }

    // 단일 수준 구조인 경우 (result.message/content)
    if (data.result && typeof data.result === "object") {
        console.log("result 객체 구조 감지");
        if (data.result.content) {
            console.log("result.content 감지");
            return String(data.result.content);
        }
        if (data.result.message) {
            console.log("result.message 감지");
            return String(data.result.message);
        }

        // 결과가 있지만 예상 구조가 아닌 경우 JSON으로 변환
        try {
            console.log("result가 비표준 구조, JSON으로 변환");
            return JSON.stringify(data.result, null, 2);
        } catch (e) {
            console.error("JSON 변환 오류:", e);
        }
    }

    // 아무것도 찾지 못했지만 데이터가 있는 경우
    if (data) {
        try {
            console.log("비표준 데이터 구조, 전체를 JSON으로 변환");
            return JSON.stringify(data, null, 2);
        } catch (e) {
            console.error("JSON 변환 오류:", e);
        }
    }

    // 직접 message 필드가 있는 경우 (추가 검사)
    if (data.message) {
        return String(data.message);
    }

    return "처리가 완료되었으나 결과가 없습니다.";
};

const RequestForm: React.FC<RequestFormProps> = ({ onTaskCreated }) => {
    const [query, setQuery] = useState("");
    const [conversationId, setConversationId] = useState<string | null>(null);
    const [messages, setMessages] = useState<(Message | ProcessMessageType)[]>(
        []
    );
    const [waitingForResponse, setWaitingForResponse] = useState(false);
    const [processedTaskIds, setProcessedTaskIds] = useState<Set<string>>(
        new Set()
    );
    const [taskSplitShown, setTaskSplitShown] = useState(false);
    const [taskGroups, setTaskGroups] = useState<TaskGroup[]>([]);

    // 마지막 요청 시간 추적
    const lastPollingTime = useRef<number>(0);
    // 폴링 간격 (밀리초)
    const pollingInterval = 2000;
    // 완료 확인 후 추가 폴링 횟수 제한
    const maxAdditionalPolls = 1;
    const additionalPollsCount = useRef<number>(0);

    // 쿼리 클라이언트 가져오기
    const queryClient = useQueryClient();

    // 대화 상태 조회
    const {
        data: conversationData,
        refetch: refetchConversation,
        remove: removeConversationQuery,
    } = useQuery(
        ["conversationStatus", conversationId],
        () => {
            // 현재 시간 체크
            const currentTime = Date.now();

            // 마지막 폴링 이후 충분한 시간이 지났는지 확인
            if (currentTime - lastPollingTime.current < pollingInterval) {
                console.log("폴링 간격 유지 중...");
                return Promise.resolve(null);
            }

            // 폴링 시간 업데이트
            lastPollingTime.current = currentTime;

            // 실제 API 호출
            return conversationId
                ? orchestratorApi.getConversationStatus(conversationId)
                : null;
        },
        {
            enabled: !!conversationId && waitingForResponse,
            refetchInterval: waitingForResponse ? pollingInterval : false,
            onSuccess: (data: ConversationStatus | null) => {
                if (!data) return;

                // 태스크 그룹화 처리
                processTaskGroups(data);

                // 태스크 분리 메시지 표시
                if (data.tasks && data.tasks.length > 0 && !taskSplitShown) {
                    displayTaskSplitMessage(data);
                }

                // 개별 태스크 처리 상태 및 결과 표시
                if (data.tasks && data.tasks.length > 0) {
                    processTasksStatus(data.tasks);
                }

                // 최종 통합 결과가 있으면 추가
                if (
                    data.status === "completed" &&
                    data.message &&
                    data.message.trim()
                ) {
                    displayFinalMessage(data);
                }

                // 모든 처리가 완료된 경우
                if (
                    data.status === "completed" ||
                    data.status === "partially_completed"
                ) {
                    // 최대 1번의 추가 폴링 허용 (누락된 결과 확인용)
                    if (additionalPollsCount.current < maxAdditionalPolls) {
                        additionalPollsCount.current++;
                        console.log(
                            `완료 후 추가 폴링 (${additionalPollsCount.current}/${maxAdditionalPolls})`
                        );
                    } else {
                        console.log("모든 폴링 완료, 대화 쿼리 제거");
                        setWaitingForResponse(false);
                        removeConversationQuery();

                        // 캐시에서도 제거하여 메모리 누수 방지
                        queryClient.removeQueries([
                            "conversationStatus",
                            conversationId,
                        ]);
                    }
                }
            },
        }
    );

    // 태스크 그룹화 처리 함수
    const processTaskGroups = (data: ConversationStatus) => {
        if (!data.tasks || data.tasks.length === 0) return;

        // 태스크를 역할 및 설명별로 그룹화
        const groups: TaskGroup[] = [];

        data.tasks.forEach((task, idx) => {
            // 태스크에 인덱스 할당 (없는 경우)
            const taskIndex = task.index !== undefined ? task.index : idx;

            // 같은 설명과 역할을 가진 그룹 찾기
            const existingGroup = groups.find(
                (g) =>
                    g.description === task.description && g.role === task.role
            );

            if (existingGroup) {
                // 기존 그룹에 추가
                existingGroup.tasks.push(task);
            } else {
                // 새 그룹 생성
                groups.push({
                    index: taskIndex,
                    description: task.description || `태스크 ${taskIndex + 1}`,
                    role: task.role || "unknown",
                    tasks: [task],
                });
            }
        });

        // 인덱스로 정렬
        groups.sort((a, b) => a.index - b.index);

        setTaskGroups(groups);
    };

    // 태스크 분할 메시지 표시 함수
    const displayTaskSplitMessage = (data: ConversationStatus) => {
        // 실행 레벨 정보 확인
        let taskDescriptions = "";
        let hasTaskDescriptions = false;

        // 태스크 분해 결과에서 자연어 설명 가져오기
        if (
            data.taskDecomposition &&
            data.taskDecomposition.tasks &&
            data.taskDecomposition.tasks.length > 0
        ) {
            taskDescriptions += "\n\n### 태스크 실행 레벨 설명\n";

            // 레벨별로 그룹화
            const tasksByLevel: {
                [key: number]: Array<{
                    description: string;
                    role: string;
                    index: number;
                    level?: number;
                }>;
            } = {};

            // 태스크를 레벨별로 그룹화
            data.taskDecomposition.tasks.forEach((task) => {
                const level = task.level ?? 0;
                if (!tasksByLevel[level]) {
                    tasksByLevel[level] = [];
                }
                tasksByLevel[level].push(task);
            });

            // 레벨별로 태스크 설명 추가
            Object.keys(tasksByLevel)
                .sort((a, b) => Number(a) - Number(b))
                .forEach((level) => {
                    taskDescriptions += `\n#### 실행 레벨 ${
                        Number(level) + 1
                    }\n`;
                    tasksByLevel[Number(level)].forEach((task) => {
                        taskDescriptions += `- ${task.description}\n`;
                    });
                });

            hasTaskDescriptions = true;
        }

        // 기존의 execution_levels 처리 로직 (자연어 설명이 없는 경우)
        if (
            !hasTaskDescriptions &&
            data.execution_levels &&
            data.execution_levels.length > 0
        ) {
            // 실행 레벨별로 태스크 그룹화해서 표시
            taskDescriptions += "\n\n### 실행 레벨 정보\n";
            data.execution_levels.forEach((levelTasks, levelIndex) => {
                taskDescriptions += `#### 실행 레벨 ${levelIndex + 1}\n`;

                levelTasks.forEach((taskIndex) => {
                    if (taskIndex >= 0 && taskIndex < data.tasks.length) {
                        const task = data.tasks[taskIndex];
                        if (task) {
                            const index =
                                task.index !== undefined
                                    ? task.index
                                    : taskIndex;
                            taskDescriptions += `- ${
                                task.description ||
                                (task.role
                                    ? `${task.role} 태스크`
                                    : "태스크 " + task.id)
                            }\n`;
                        }
                    }
                });
            });

            hasTaskDescriptions = true;
        }

        // 실행 레벨 정보가 없는 경우 기본 태스크 목록으로 대체
        if (!hasTaskDescriptions) {
            taskDescriptions = "\n\n";
            taskDescriptions += data.tasks
                .map((task: TaskInfo, idx: number) => {
                    const index = task.index !== undefined ? task.index : idx;
                    return `- 태스크 ${index + 1}: ${
                        task.description ||
                        (task.role
                            ? `${task.role} 태스크`
                            : "태스크 " + task.id)
                    }`;
                })
                .join("\n");
        }

        setMessages((prev) => [
            ...prev,
            {
                role: "system",
                processType: "task_split",
                content: `## 태스크 분리 완료${taskDescriptions}`,
                timestamp: new Date(),
                conversationId: conversationId || undefined,
            } as ProcessMessageType,
        ]);

        setTaskSplitShown(true);
    };

    // 최종 통합 결과 메시지 표시 함수
    const displayFinalMessage = (data: ConversationStatus) => {
        // 이미 최종 결과가 표시되었는지 확인
        const existingResult = messages.find(
            (msg) =>
                msg.role === "assistant" &&
                msg.conversationId === data.conversation_id &&
                msg.finalResult === true
        );

        if (!existingResult && data.message) {
            console.log(
                "최종 통합 결과 메시지 추가:",
                data.message.substring(0, 50) + "..."
            );

            setMessages((prev) => [
                ...prev,
                {
                    role: "assistant" as const,
                    content: data.message || "",
                    timestamp: new Date(),
                    conversationId: data.conversation_id,
                    finalResult: true,
                } as Message,
            ]);
        }
    };

    // 태스크 상태 처리 함수
    const processTasksStatus = (tasks: TaskInfo[]) => {
        console.log("태스크 상태 처리:", tasks.length, "개 태스크");

        tasks.forEach((task: TaskInfo, idx: number) => {
            // 태스크 인덱스 확인
            const taskIndex = task.index !== undefined ? task.index : idx;

            console.log(
                `태스크 ${taskIndex}(${idx}): ${task.id}, 상태: ${task.status}, 역할: ${task.role}`
            );

            // 이미 처리된 태스크인지 확인 (이미 메시지로 추가된 경우 건너뛰기)
            const existingTaskMessage = messages.find(
                (msg) =>
                    "processType" in msg &&
                    msg.processType === "agent_result" &&
                    msg.taskId === task.id
            );

            if (existingTaskMessage) {
                console.log(
                    `태스크 ${task.id}는 이미 메시지로 표시됨, 건너뛰기`
                );
                return;
            }

            // 처리 중 상태 표시
            if (task.status === "processing") {
                displayProcessingMessage(task, taskIndex);
            }

            // 완료된 태스크 결과 표시
            if (task.status === "completed" && task.result) {
                console.log(
                    `태스크 ${task.id} 완료됨, 결과 표시 시도, 역할: ${task.role}`
                );
                displayCompletedResult(task, taskIndex);
            }
        });
    };

    // 처리중인 메시지 표시 함수
    const displayProcessingMessage = (task: TaskInfo, taskIndex: number) => {
        // 이미 처리 중 메시지가 있는지 확인
        const existingMsg = messages.find(
            (msg) =>
                "processType" in msg &&
                msg.processType === "agent_processing" &&
                msg.taskId === task.id
        );

        if (existingMsg) return;

        setMessages((prev) => [
            ...prev,
            {
                role: "system",
                processType: "agent_processing",
                content: `${task.role || ""} 태스크를 처리 중입니다...`,
                timestamp: new Date(),
                conversationId: conversationId || undefined,
                taskId: task.id,
                agentRole: task.role,
                status: "processing",
                taskIndex: taskIndex,
                taskDescription: task.description,
            } as ProcessMessageType,
        ]);
    };

    // 완료된 결과 표시 함수
    const displayCompletedResult = (task: TaskInfo, taskIndex: number) => {
        // 이미 결과 메시지가 있는지 확인
        const existingResult = messages.find(
            (msg) =>
                "processType" in msg &&
                msg.processType === "agent_result" &&
                msg.taskId === task.id
        );

        // 이미 있으면 업데이트하지 않음
        if (existingResult) {
            console.log(`태스크 ${task.id}의 결과는 이미 표시됨, 건너뛰기`);
            return;
        }

        // 결과 메시지 추출
        let resultContent = extractResultContent(task.result);

        // 로그 추가
        console.log(
            `태스크 ${taskIndex} 완료: ${task.id}, 결과 길이: ${
                resultContent ? resultContent.length : 0
            }, 역할: ${task.role}`
        );

        // 결과가 있으면 메시지 추가
        if (resultContent) {
            setMessages((prev) => {
                // 처리 중 메시지 찾기
                const processingIndex = prev.findIndex(
                    (msg) =>
                        "processType" in msg &&
                        msg.processType === "agent_processing" &&
                        msg.taskId === task.id
                );

                // 새 메시지 배열 생성
                const newMessages = [...prev];

                // 처리 중 메시지가 있으면 상태 업데이트
                if (processingIndex >= 0) {
                    const processingMsg = newMessages[
                        processingIndex
                    ] as ProcessMessageType;
                    newMessages[processingIndex] = {
                        ...processingMsg,
                        status: "completed",
                    };
                }

                // 결과 메시지 생성
                const resultMessage: ProcessMessageType = {
                    role: "system",
                    processType: "agent_result",
                    content: resultContent,
                    timestamp: new Date(),
                    conversationId: conversationId || undefined,
                    taskId: task.id,
                    agentRole: task.role,
                    status: "completed",
                    taskIndex: taskIndex,
                    taskDescription: task.description,
                };

                console.log(
                    `태스크 ${task.id}의 결과 메시지 추가: ${task.role}`
                );

                // 결과 메시지 추가
                return [...newMessages, resultMessage];
            });
        } else {
            console.log(`태스크 ${task.id}의 결과가 없거나 추출할 수 없음`);
        }
    };

    // 결과 콘텐츠 추출 함수
    const extractResultContent = (result: any): string => {
        if (!result) return "";

        console.log("결과 추출 시도:", result);

        // 결과가 직접 문자열인 경우
        if (typeof result === "string") {
            return result;
        }

        // writer 에이전트 결과 처리
        if (result.result && result.result.content) {
            console.log(
                "writer 에이전트 결과 형식 감지:",
                result.result.content.substring(0, 50) + "..."
            );
            return result.result.content;
        }

        // 코드 생성기 결과 처리
        if (result.code_files) {
            let codeContent = "";

            if (result.explanation) {
                codeContent += `### 설명\n${result.explanation}\n\n`;
            }

            // 코드 파일 처리
            for (const [filename, code] of Object.entries(result.code_files)) {
                codeContent += `### ${filename}\n\`\`\`${
                    result.language || "python"
                }\n${code}\n\`\`\`\n\n`;
            }

            return codeContent;
        }

        // 일반적인 중첩 구조 처리
        if (result.content) {
            return result.content;
        }

        if (result.message) {
            return result.message;
        }

        if (result.result) {
            if (typeof result.result === "string") {
                return result.result;
            }
            if (result.result.content) {
                return result.result.content;
            }
            if (result.result.message) {
                return result.result.message;
            }
        }

        // 객체인 경우 JSON으로 변환
        try {
            return JSON.stringify(result, null, 2);
        } catch (e) {
            console.error("JSON 변환 오류:", e);
            return "결과 변환 중 오류가 발생했습니다.";
        }
    };

    // 요청 처리 뮤테이션
    const queryMutation = useMutation(orchestratorApi.processQuery, {
        onSuccess: (response) => {
            // response가 객체인 경우 conversation_id를 taskId로 사용
            const taskId =
                typeof response === "object"
                    ? response.conversation_id
                    : response;

            // 처음 요청인 경우 conversation_id 저장
            if (!conversationId) {
                setConversationId(taskId);
            }

            // 태스크 분리 상태 초기화
            setTaskSplitShown(false);
            // 처리된 태스크 ID 초기화
            setProcessedTaskIds(new Set());
            // 태스크 그룹 초기화
            setTaskGroups([]);
            // 추가 폴링 카운터 초기화
            additionalPollsCount.current = 0;

            onTaskCreated(taskId);
            setQuery("");

            // 응답 대기 상태로 설정
            setWaitingForResponse(true);
            // 폴링 시간 초기화
            lastPollingTime.current = Date.now();
        },
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        if (!query.trim()) return;

        // 사용자 메시지 추가
        setMessages((prev) => [
            ...prev,
            {
                role: "user",
                content: query,
                timestamp: new Date(),
                conversationId: conversationId || undefined,
            },
        ]);

        // 기본 요청 객체
        const request: QueryRequest = {
            query: query,
            conversation_id: conversationId || Date.now().toString(), // 기존 대화 ID 또는 새로운 ID
        };

        // 에이전트 설정 추가 - 서비스에서 모든 설정 가져오기
        const allConfigs = agentConfigService.getAllConfigs();
        if (Object.keys(allConfigs).length > 0) {
            request.agent_configs = allConfigs;
        }

        queryMutation.mutate(request);
    };

    // 마크다운 내용 렌더링 (테이블 처리 포함)
    const renderMessageContent = (content: string) => {
        if (!content) return null;

        // 마크다운 테이블이 포함된 경우 HTML로 변환
        if (content.includes("|") && content.includes("\n|")) {
            const htmlContent = convertMarkdownTablesToHtml(content);
            return <div dangerouslySetInnerHTML={{ __html: htmlContent }} />;
        } else {
            // 일반 마크다운인 경우
            return (
                <div className="prose prose-sm max-w-none">
                    <ReactMarkdown>{content}</ReactMarkdown>
                </div>
            );
        }
    };

    // 각 메시지 렌더링
    const renderMessage = (
        message: Message | ProcessMessageType,
        index: number
    ) => {
        // ProcessMessage 타입 체크
        if ("processType" in message) {
            return (
                <ProcessMessage
                    key={index}
                    type={message.processType}
                    role={message.agentRole}
                    content={message.content}
                    timestamp={message.timestamp}
                    className="mb-2"
                    taskIndex={message.taskIndex}
                    taskDescription={message.taskDescription}
                />
            );
        }

        // 일반 메시지
        return (
            <div
                key={index}
                className={`p-3 rounded-lg mb-4 ${
                    message.role === "user"
                        ? "bg-blue-100 ml-auto max-w-3/4"
                        : "bg-gray-100 mr-auto max-w-5/6 w-5/6"
                }`}
            >
                <div className="text-sm">
                    {renderMessageContent(message.content)}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                    {message.timestamp.toLocaleTimeString()}
                </div>
            </div>
        );
    };

    // 이벤트 구독 설정
    useEffect(() => {
        // 최종 결과 이벤트 구독
        const handleFinalResult = (data: any) => {
            console.log("최종 결과 이벤트 수신:", data);

            // 이미 시스템 메시지로 최종 결과가 표시되었는지 확인
            const existingResult = messages.find(
                (msg) =>
                    msg.role === "assistant" &&
                    msg.conversationId === data.conversationId &&
                    msg.finalResult === true
            );

            if (!existingResult) {
                setMessages((prev) => [
                    ...prev,
                    {
                        role: "assistant",
                        content: data.content,
                        timestamp: new Date(data.timestamp) || new Date(),
                        conversationId: data.conversationId,
                        finalResult: true,
                    },
                ]);
            }
        };

        eventEmitter.on("finalResult", handleFinalResult);

        // 컴포넌트 언마운트 시 이벤트 구독 해제
        return () => {
            eventEmitter.off("finalResult", handleFinalResult);
        };
    }, [messages]);

    return (
        <div className="bg-white rounded-lg shadow-md p-6 flex flex-col h-full">
            <h2 className="text-xl font-bold mb-4">대화</h2>

            {/* 메시지 목록 */}
            <div className="flex-grow overflow-y-auto mb-4 space-y-2 max-h-96">
                {messages.length === 0 ? (
                    <div className="text-center text-gray-500 py-8">
                        새로운 대화를 시작하세요
                    </div>
                ) : (
                    messages.map((message, index) =>
                        renderMessage(message, index)
                    )
                )}

                {/* 로딩 표시 */}
                {waitingForResponse && !taskSplitShown && (
                    <div className="bg-gray-100 p-3 rounded-lg mr-auto max-w-5/6 w-5/6">
                        <div className="flex items-center justify-start space-x-2">
                            <div className="w-2 h-2 rounded-full bg-gray-400 animate-bounce"></div>
                            <div
                                className="w-2 h-2 rounded-full bg-gray-400 animate-bounce"
                                style={{ animationDelay: "0.2s" }}
                            ></div>
                            <div
                                className="w-2 h-2 rounded-full bg-gray-400 animate-bounce"
                                style={{ animationDelay: "0.4s" }}
                            ></div>
                            <span className="text-sm text-gray-500">
                                태스크 분리 중...
                            </span>
                        </div>
                    </div>
                )}
            </div>

            {/* 입력 폼 */}
            <form onSubmit={handleSubmit} className="mt-auto">
                <div className="flex space-x-2">
                    <input
                        type="text"
                        className="flex-grow rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-200 p-2"
                        placeholder="메시지를 입력하세요..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        disabled={waitingForResponse || queryMutation.isLoading}
                    />
                    <button
                        type="submit"
                        className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={
                            queryMutation.isLoading ||
                            waitingForResponse ||
                            !query.trim()
                        }
                    >
                        {queryMutation.isLoading ? (
                            <span>전송 중...</span>
                        ) : (
                            <span>전송</span>
                        )}
                    </button>
                </div>
            </form>

            {/* 에러 메시지 표시 */}
            {queryMutation.isError && (
                <div className="mt-4 text-red-600 text-sm">
                    요청 처리 중 오류가 발생했습니다. 다시 시도해주세요.
                </div>
            )}
        </div>
    );
};

export default RequestForm;
