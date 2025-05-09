import React, { useState, useEffect } from "react";
import axios from "axios";
import {
    llmConfigService,
    AVAILABLE_LLM_MODELS,
    LLMConfig,
} from "../services/LLMConfigService";
import LLMStatusLog from "./LLMStatusLog";
import { llmConfigApi } from "../api/llmConfig";

interface LLMConfigManagerProps {
    selectedComponent?: string; // 특정 컴포넌트만 표시하는 옵션
}

const LLMConfigManager: React.FC<LLMConfigManagerProps> = ({
    selectedComponent,
}) => {
    const [components, setComponents] = useState<
        Array<{
            id: string;
            name: string;
            description: string;
        }>
    >([]);

    const [configs, setConfigs] = useState<Record<string, LLMConfig>>({});
    const [saveStatus, setSaveStatus] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(true);
    const [showAdvanced, setShowAdvanced] = useState<Record<string, boolean>>(
        {}
    );
    const [showLog, setShowLog] = useState<boolean>(false);
    const [testResults, setTestResults] = useState<Record<string, any>>({});
    const [isTestingModel, setIsTestingModel] = useState<
        Record<string, boolean>
    >({});

    // 컴포넌트 로드 시 초기화
    useEffect(() => {
        loadComponents();
    }, [selectedComponent]);

    // 컴포넌트 및 에이전트 목록 로드
    const loadComponents = async () => {
        try {
            // 에이전트 목록 가져오기
            const response = await axios.get("/api/registry/agents");
            const agents = response.data.agents || response.data;

            // 기존 컴포넌트 목록 가져오기
            const baseComponents = llmConfigService.getComponents();

            // 에이전트 목록 추가
            const uniqueAgentRoles = new Set<string>();
            agents.forEach((agent: any) => {
                uniqueAgentRoles.add(agent.role);
            });

            const allComponents = [...baseComponents];

            // 에이전트 역할을 컴포넌트로 추가
            uniqueAgentRoles.forEach((role) => {
                // 이미 있는 컴포넌트는 추가하지 않음
                if (!allComponents.some((c) => c.id === role)) {
                    allComponents.push({
                        id: role,
                        name: role
                            .replace(/_/g, " ")
                            .replace(/\b\w/g, (l) => l.toUpperCase()),
                        description: `${role} 에이전트`,
                    });
                }
            });

            // 특정 컴포넌트만 표시하는 경우 필터링
            const filteredComponents = selectedComponent
                ? allComponents.filter((c) => c.id === selectedComponent)
                : allComponents;

            setComponents(filteredComponents);

            // 설정 로드
            const loadedConfigs = llmConfigService.getAllConfigs();
            setConfigs(loadedConfigs);

            // 각 컴포넌트에 대해 필요한 기본 설정 초기화
            filteredComponents.forEach((component) => {
                if (!loadedConfigs[component.id]) {
                    llmConfigService.updateConfig(component.id, {
                        componentName: component.id,
                        modelName: "gpt-4o-mini",
                    });
                }
            });

            // 최종 설정 상태 다시 로드
            setConfigs(llmConfigService.getAllConfigs());
            setLoading(false);
        } catch (error) {
            console.error("컴포넌트 로드 오류:", error);
            setLoading(false);
        }
    };

    // 설정 변경 핸들러
    const handleConfigChange = (
        componentId: string,
        key: string,
        value: any
    ) => {
        // 설정 업데이트
        llmConfigService.updateConfig(componentId, { [key]: value });

        // 상태 업데이트
        setConfigs(llmConfigService.getAllConfigs());

        // 저장 상태 표시
        setSaveStatus({
            ...saveStatus,
            [componentId]: "저장됨",
        });

        // 3초 후 저장 상태 메시지 제거
        setTimeout(() => {
            setSaveStatus((prev) => {
                const newStatus = { ...prev };
                delete newStatus[componentId];
                return newStatus;
            });
        }, 3000);

        // 서버에 설정 변경 알림 (API 호출)
        const config = llmConfigService.getConfig(componentId);
        if (config) {
            llmConfigApi
                .updateConfig(componentId, config)
                .then(() => {
                    console.log(`${componentId} LLM 설정이 서버에 업데이트됨`);
                })
                .catch((error) => {
                    console.error("LLM 설정 저장 오류:", error);
                });
        }
    };

    // 고급 설정 토글
    const toggleAdvanced = (componentId: string) => {
        setShowAdvanced((prev) => ({
            ...prev,
            [componentId]: !prev[componentId],
        }));
    };

    // 로그 토글
    const toggleLog = () => {
        setShowLog(!showLog);
    };

    // LLM 모델 연결 테스트
    const testModelConnection = async (
        componentId: string,
        modelName: string
    ) => {
        // 테스트 중 상태 설정
        setIsTestingModel({
            ...isTestingModel,
            [componentId]: true,
        });

        // 이전 테스트 결과 지우기
        setTestResults((prev) => {
            const newResults = { ...prev };
            delete newResults[componentId];
            return newResults;
        });

        try {
            // 테스트할 컴포넌트에 맞게 서비스 선택
            // (오케스트레이터와 브로커에만 테스트 엔드포인트가 구현됨)
            const testComponent =
                componentId === "broker" ? "broker" : "orchestrator";

            // 현재 설정된 temperature와 maxTokens 값 가져오기
            const config = configs[componentId] || {};
            const temperature = config.temperature || 0.7;
            const maxTokens = config.maxTokens || 1024;

            // API 호출하여 모델 테스트
            const result = await llmConfigApi.testLLMConnection(
                modelName,
                testComponent,
                temperature,
                maxTokens
            );

            // 테스트 결과 저장
            setTestResults({
                ...testResults,
                [componentId]: result,
            });
        } catch (error) {
            // 오류 발생 시 오류 정보 저장
            setTestResults({
                ...testResults,
                [componentId]: {
                    success: false,
                    error:
                        error instanceof Error
                            ? error.message
                            : "알 수 없는 오류",
                    model: modelName,
                },
            });
        } finally {
            // 테스트 완료 후 상태 해제
            setIsTestingModel({
                ...isTestingModel,
                [componentId]: false,
            });
        }
    };

    if (loading) {
        return <div className="p-4">LLM 설정 로드 중...</div>;
    }

    return (
        <div
            className={
                selectedComponent ? "" : "p-4 bg-white shadow rounded-lg"
            }
        >
            {!selectedComponent && (
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-xl font-bold">LLM 모델 설정</h2>
                    <button
                        onClick={toggleLog}
                        className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded text-sm"
                    >
                        {showLog ? "로그 숨기기" : "로그 보기"}
                    </button>
                </div>
            )}

            {/* 로그 보기 */}
            {showLog && (
                <div className="mb-6">
                    <LLMStatusLog />
                </div>
            )}

            {components.length === 0 ? (
                <div className="text-gray-500">표시할 설정이 없습니다.</div>
            ) : (
                <div className="space-y-6">
                    {components.map((component) => {
                        const config = configs[component.id] || {
                            componentName: component.id,
                            modelName: "gpt-4o-mini",
                        };

                        return (
                            <div
                                key={component.id}
                                className="border border-gray-200 rounded-lg p-4"
                            >
                                <div className="flex justify-between items-center mb-3">
                                    <h3 className="font-medium text-lg">
                                        {component.name}
                                    </h3>
                                    {saveStatus[component.id] && (
                                        <span className="text-sm text-green-600 bg-green-100 px-2 py-1 rounded">
                                            {saveStatus[component.id]}
                                        </span>
                                    )}
                                </div>

                                <p className="text-sm text-gray-600 mb-4">
                                    {component.description}
                                </p>

                                <div className="space-y-3">
                                    {/* 모델 선택 */}
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">
                                            LLM 모델
                                        </label>
                                        <div className="flex gap-2">
                                            <select
                                                value={config.modelName}
                                                onChange={(e) =>
                                                    handleConfigChange(
                                                        component.id,
                                                        "modelName",
                                                        e.target.value
                                                    )
                                                }
                                                className="flex-1 border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500"
                                            >
                                                {AVAILABLE_LLM_MODELS.map(
                                                    (model) => (
                                                        <option
                                                            key={model.id}
                                                            value={model.id}
                                                        >
                                                            {model.name} (
                                                            {model.provider})
                                                        </option>
                                                    )
                                                )}
                                            </select>
                                            <button
                                                onClick={() =>
                                                    testModelConnection(
                                                        component.id,
                                                        config.modelName
                                                    )
                                                }
                                                disabled={
                                                    isTestingModel[component.id]
                                                }
                                                className={`px-3 py-1 text-sm rounded 
                                                    ${
                                                        isTestingModel[
                                                            component.id
                                                        ]
                                                            ? "bg-gray-200 text-gray-500"
                                                            : "bg-blue-100 text-blue-700 hover:bg-blue-200"
                                                    }`}
                                            >
                                                {isTestingModel[component.id]
                                                    ? "테스트 중..."
                                                    : "모델 테스트"}
                                            </button>
                                        </div>
                                        <p className="mt-1 text-xs text-gray-500">
                                            {
                                                AVAILABLE_LLM_MODELS.find(
                                                    (m) =>
                                                        m.id ===
                                                        config.modelName
                                                )?.description
                                            }
                                        </p>

                                        {/* 테스트 결과 표시 */}
                                        {testResults[component.id] && (
                                            <div
                                                className={`mt-2 p-2 rounded text-sm ${
                                                    testResults[component.id]
                                                        .success
                                                        ? "bg-green-50 text-green-700 border border-green-100"
                                                        : "bg-red-50 text-red-700 border border-red-100"
                                                }`}
                                            >
                                                <div className="font-medium">
                                                    {testResults[component.id]
                                                        .success
                                                        ? "✅ 모델 연결 테스트 성공"
                                                        : "❌ 모델 연결 테스트 실패"}
                                                </div>
                                                {testResults[component.id]
                                                    .success && (
                                                    <div className="text-xs mt-1">
                                                        응답:{" "}
                                                        {testResults[
                                                            component.id
                                                        ].response?.substring(
                                                            0,
                                                            100
                                                        )}
                                                        {testResults[
                                                            component.id
                                                        ].response?.length > 100
                                                            ? "..."
                                                            : ""}
                                                        <br />
                                                        응답 시간:{" "}
                                                        {testResults[
                                                            component.id
                                                        ].execution_time.toFixed(
                                                            2
                                                        )}
                                                        초
                                                    </div>
                                                )}
                                                {!testResults[component.id]
                                                    .success && (
                                                    <div className="text-xs mt-1">
                                                        오류:{" "}
                                                        {testResults[
                                                            component.id
                                                        ].error ||
                                                            testResults[
                                                                component.id
                                                            ].message}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>

                                    {/* 고급 설정 토글 버튼 */}
                                    <div className="pt-2">
                                        <button
                                            type="button"
                                            onClick={() =>
                                                toggleAdvanced(component.id)
                                            }
                                            className="text-sm text-blue-600 hover:text-blue-800"
                                        >
                                            {showAdvanced[component.id]
                                                ? "기본 설정으로 돌아가기"
                                                : "고급 설정 보기"}
                                        </button>
                                    </div>

                                    {/* 고급 설정 */}
                                    {showAdvanced[component.id] && (
                                        <div className="mt-3 pt-3 border-t border-gray-200 space-y-3">
                                            {/* Temperature 설정 */}
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                                    Temperature:{" "}
                                                    {config.temperature || 0.7}
                                                </label>
                                                <input
                                                    type="range"
                                                    min="0"
                                                    max="1"
                                                    step="0.1"
                                                    value={
                                                        config.temperature ||
                                                        0.7
                                                    }
                                                    onChange={(e) =>
                                                        handleConfigChange(
                                                            component.id,
                                                            "temperature",
                                                            parseFloat(
                                                                e.target.value
                                                            )
                                                        )
                                                    }
                                                    className="w-full"
                                                />
                                                <p className="mt-1 text-xs text-gray-500">
                                                    낮을수록 더 일관된 결과,
                                                    높을수록 더 다양한 결과가
                                                    생성됩니다.
                                                </p>
                                            </div>

                                            {/* Max Tokens 설정 */}
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                                    최대 토큰 수
                                                </label>
                                                <input
                                                    type="number"
                                                    min="100"
                                                    max="8000"
                                                    step="100"
                                                    value={
                                                        config.maxTokens || 1024
                                                    }
                                                    onChange={(e) =>
                                                        handleConfigChange(
                                                            component.id,
                                                            "maxTokens",
                                                            parseInt(
                                                                e.target.value
                                                            )
                                                        )
                                                    }
                                                    className="w-full border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500"
                                                />
                                                <p className="mt-1 text-xs text-gray-500">
                                                    LLM이 생성할 수 있는 최대
                                                    토큰 수입니다.
                                                </p>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};

export default LLMConfigManager;
