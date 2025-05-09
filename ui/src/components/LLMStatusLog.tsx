import React, { useState, useEffect, useRef } from "react";
import { llmConfigService } from "../services/LLMConfigService";
import { llmConfigApi } from "../api/llmConfig";

interface LLMStatusLogProps {
    maxLogEntries?: number;
}

interface LogEntry {
    timestamp: number;
    component: string;
    modelName: string;
    message: string;
    status: "success" | "error" | "info";
}

const LLMStatusLog: React.FC<LLMStatusLogProps> = ({ maxLogEntries = 30 }) => {
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [isAutoRefresh, setIsAutoRefresh] = useState(true);
    const logEndRef = useRef<HTMLDivElement>(null);

    // 초기 로그 메시지 추가
    useEffect(() => {
        const configs = llmConfigService.getAllConfigs();
        const initialLogs: LogEntry[] = [];

        Object.entries(configs).forEach(([component, config]) => {
            initialLogs.push({
                timestamp: Date.now(),
                component,
                modelName: config.modelName,
                message: `${component}에 ${config.modelName} 모델이 설정되었습니다.`,
                status: "info",
            });
        });

        setLogs(initialLogs);

        // 브로커 및 오케스트레이터의 현재 LLM 상태 확인
        fetchLLMStatus();

        // 주기적인 상태 확인 (10초마다)
        const intervalId = setInterval(() => {
            if (isAutoRefresh) {
                fetchLLMStatus();
            }
        }, 10000);

        return () => clearInterval(intervalId);
    }, [isAutoRefresh]);

    // 로그가 추가될 때마다 자동 스크롤
    useEffect(() => {
        if (logEndRef.current) {
            logEndRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [logs]);

    // LLM 상태 가져오기
    const fetchLLMStatus = async () => {
        try {
            // 오케스트레이터 상태 확인 - API 클라이언트 사용
            try {
                const orchestratorStatus =
                    await llmConfigApi.getComponentConfig("orchestrator");

                if (orchestratorStatus.success) {
                    addLogEntry({
                        component: "orchestrator",
                        modelName:
                            orchestratorStatus.config?.modelName ||
                            "알 수 없음",
                        message: "오케스트레이터 LLM 상태 확인 완료",
                        status: "success",
                    });
                }
            } catch (err) {
                console.error("오케스트레이터 상태 확인 오류:", err);
                addLogEntry({
                    component: "orchestrator",
                    modelName: "None",
                    message: "오케스트레이터 LLM 상태 확인 중 오류 발생",
                    status: "error",
                });
            }

            // 브로커 상태 확인 - API 클라이언트 사용
            try {
                const brokerStatus = await llmConfigApi.getBrokerLLMStatus();

                if (brokerStatus.success) {
                    addLogEntry({
                        component: "broker",
                        modelName: brokerStatus.model || "알 수 없음",
                        message: "브로커 LLM 상태 확인 완료",
                        status: "success",
                    });
                }
            } catch (err) {
                console.error("브로커 상태 확인 오류:", err);
                addLogEntry({
                    component: "broker",
                    modelName: "None",
                    message: "브로커 LLM 상태 확인 중 오류 발생",
                    status: "error",
                });
            }
        } catch (error) {
            console.error("LLM 상태 확인 오류:", error);
            addLogEntry({
                component: "system",
                modelName: "None",
                message: "LLM 상태 확인 중 오류 발생",
                status: "error",
            });
        }
    };

    // 로그 항목 추가
    const addLogEntry = (entry: Omit<LogEntry, "timestamp">) => {
        setLogs((prevLogs) => {
            const newLogs = [...prevLogs, { ...entry, timestamp: Date.now() }];

            // 최대 로그 개수 제한
            return newLogs.slice(-maxLogEntries);
        });
    };

    // 시간 포맷팅
    const formatTime = (timestamp: number) => {
        const date = new Date(timestamp);
        return date.toLocaleTimeString("ko-KR", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
        });
    };

    // 로그 지우기
    const clearLogs = () => {
        setLogs([
            {
                timestamp: Date.now(),
                component: "system",
                modelName: "None",
                message: "로그가 지워졌습니다.",
                status: "info",
            },
        ]);
    };

    return (
        <div className="bg-gray-50 border rounded-lg p-4">
            <div className="flex justify-between items-center mb-3">
                <h3 className="font-medium">LLM 사용 로그</h3>
                <div className="flex space-x-2">
                    <button
                        onClick={() => setIsAutoRefresh(!isAutoRefresh)}
                        className={`px-2 py-1 text-xs rounded ${
                            isAutoRefresh
                                ? "bg-green-100 text-green-700"
                                : "bg-gray-200 text-gray-700"
                        }`}
                    >
                        {isAutoRefresh ? "자동 갱신 중" : "자동 갱신 중지"}
                    </button>
                    <button
                        onClick={fetchLLMStatus}
                        className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded"
                    >
                        상태 확인
                    </button>
                    <button
                        onClick={clearLogs}
                        className="px-2 py-1 text-xs bg-gray-200 text-gray-700 rounded"
                    >
                        지우기
                    </button>
                </div>
            </div>

            <div className="bg-gray-800 text-gray-100 rounded p-3 h-60 overflow-y-auto font-mono text-xs">
                {logs.length === 0 ? (
                    <div className="text-gray-500 italic">로그가 없습니다.</div>
                ) : (
                    logs.map((log, index) => (
                        <div
                            key={index}
                            className={`mb-1 ${
                                log.status === "error"
                                    ? "text-red-400"
                                    : log.status === "success"
                                    ? "text-green-400"
                                    : "text-blue-400"
                            }`}
                        >
                            <span className="text-gray-500">
                                [{formatTime(log.timestamp)}]
                            </span>{" "}
                            <span className="text-yellow-400">
                                [{log.component}]
                            </span>{" "}
                            <span className="text-purple-400">
                                [{log.modelName}]
                            </span>{" "}
                            {log.message}
                        </div>
                    ))
                )}
                <div ref={logEndRef} />
            </div>
        </div>
    );
};

export default LLMStatusLog;
