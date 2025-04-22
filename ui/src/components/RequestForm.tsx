import React, { useState } from "react";
import { useMutation } from "react-query";
import { orchestratorApi } from "../api/orchestrator";
import { brokerApi } from "../api/broker";
import { QueryRequest } from "../types";

// 샘플 시나리오 목록
const SAMPLE_SCENARIOS = [
    {
        id: "scenario1",
        name: "마케팅 동향 리포트",
        description: "최신 디지털 마케팅 동향에 대한 보고서 작성",
        prompt: "최신 디지털 마케팅 동향을 조사하고 보고서로 작성해줘.",
    },
    {
        id: "scenario2",
        name: "제품 경쟁 분석",
        description: "특정 제품의 경쟁사 비교 분석",
        prompt: "스마트폰 시장의 최신 제품들을 비교 분석해줘.",
    },
    {
        id: "scenario3",
        name: "기술 문서 요약",
        description: "긴 기술 문서를 요약",
        prompt: "인공지능의 최신 발전 동향을 조사하고 핵심 내용만 요약해줘.",
    },
];

interface RequestFormProps {
    onTaskCreated: (taskId: string) => void;
}

const RequestForm: React.FC<RequestFormProps> = ({ onTaskCreated }) => {
    const [query, setQuery] = useState("");
    const [selectedScenario, setSelectedScenario] = useState<string | null>(
        null
    );

    const queryMutation = useMutation(orchestratorApi.processQuery, {
        onSuccess: (response) => {
            // response가 객체인 경우 conversation_id를 taskId로 사용
            const taskId =
                typeof response === "object"
                    ? response.conversation_id
                    : response;
            onTaskCreated(taskId);
            setQuery("");
            setSelectedScenario(null);
        },
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        const request: QueryRequest = {
            query: selectedScenario
                ? SAMPLE_SCENARIOS.find((s) => s.id === selectedScenario)
                      ?.prompt || query
                : query,
            conversation_id: Date.now().toString(), // 임시 대화 ID
        };

        queryMutation.mutate(request);
    };

    // 시나리오 선택 핸들러
    const handleScenarioSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const scenarioId = e.target.value;
        setSelectedScenario(scenarioId);

        if (scenarioId) {
            const scenario = SAMPLE_SCENARIOS.find((s) => s.id === scenarioId);
            if (scenario) {
                setQuery(scenario.prompt);
            }
        }
    };

    return (
        <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-bold mb-4">새로운 요청</h2>

            <form onSubmit={handleSubmit}>
                {/* 시나리오 선택 드롭다운 */}
                <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                        샘플 시나리오 선택
                    </label>
                    <select
                        className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-200 p-2"
                        value={selectedScenario || ""}
                        onChange={handleScenarioSelect}
                    >
                        <option value="">직접 입력</option>
                        {SAMPLE_SCENARIOS.map((scenario) => (
                            <option key={scenario.id} value={scenario.id}>
                                {scenario.name}
                            </option>
                        ))}
                    </select>
                </div>

                {/* 요청 텍스트 입력 */}
                <div className="mb-4">
                    <label
                        htmlFor="request"
                        className="block text-sm font-medium text-gray-700 mb-1"
                    >
                        요청 내용
                    </label>
                    <textarea
                        id="request"
                        className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring focus:ring-blue-200 p-2"
                        rows={5}
                        placeholder="처리할 요청을 입력해주세요. (예: '최신 AI 기술 동향을 조사하고 보고서로 작성해줘')"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                    ></textarea>
                </div>

                {/* 제출 버튼 */}
                <div className="text-right">
                    <button
                        type="submit"
                        className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={queryMutation.isLoading || !query.trim()}
                    >
                        {queryMutation.isLoading ? (
                            <span>처리 중...</span>
                        ) : (
                            <span>요청 제출</span>
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

            {/* 선택된 시나리오 정보 표시 */}
            {selectedScenario && (
                <div className="mt-4 bg-gray-50 p-3 rounded-md text-sm">
                    <p className="font-medium">
                        {
                            SAMPLE_SCENARIOS.find(
                                (s) => s.id === selectedScenario
                            )?.name
                        }
                    </p>
                    <p className="text-gray-600 mt-1">
                        {
                            SAMPLE_SCENARIOS.find(
                                (s) => s.id === selectedScenario
                            )?.description
                        }
                    </p>
                </div>
            )}
        </div>
    );
};

export default RequestForm;
