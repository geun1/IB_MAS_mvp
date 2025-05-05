import React, { useState, useEffect } from "react";
import axios from "axios";
import { agentConfigService } from "../services/AgentConfigService";
import { agentEnablementService } from "../services/AgentEnablementService";

interface ConfigParam {
    name: string;
    description: string;
    required: boolean;
    type: string;
    is_secret?: boolean;
}

interface AgentConfig {
    role: string;
    config_params: ConfigParam[];
    values: Record<string, string>;
    id?: string; // 에이전트 ID 추가
}

// 에이전트 역할별 설정 매핑
const AGENT_CONFIG_MAPPINGS: Record<string, ConfigParam[]> = {
    // web_search 에이전트는 Google Custom Search API 설정이 필요
    web_search: [
        {
            name: "api_key",
            description: "Google Custom Search API Key",
            required: true,
            type: "string",
            is_secret: true,
        },
        {
            name: "cx",
            description: "Google Custom Search Engine ID",
            required: true,
            type: "string",
        },
    ],
    // 필요시 다른 에이전트 설정 추가
};

// 설정 상태 표시 뱃지 컴포넌트
const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
    let bgColor = "bg-gray-100";
    let textColor = "text-gray-600";
    let label = "미설정";

    switch (status) {
        case "configured":
            bgColor = "bg-green-100";
            textColor = "text-green-600";
            label = "설정 완료";
            break;
        case "incomplete":
            bgColor = "bg-yellow-100";
            textColor = "text-yellow-600";
            label = "일부 설정";
            break;
        case "not_found":
            bgColor = "bg-red-100";
            textColor = "text-red-600";
            label = "미설정";
            break;
        default:
            break;
    }

    return (
        <span
            className={`text-xs font-medium ${textColor} ${bgColor} px-2 py-1 rounded-full`}
        >
            {label}
        </span>
    );
};

// 스위치 토글 컴포넌트
const ToggleSwitch: React.FC<{
    isEnabled: boolean;
    onChange: () => void;
    label?: string;
}> = ({ isEnabled, onChange, label }) => {
    return (
        <div className="flex items-center">
            {label && <span className="mr-2 text-sm">{label}</span>}
            <button
                onClick={onChange}
                className={`relative inline-flex items-center h-6 rounded-full w-11 transition-colors focus:outline-none ${
                    isEnabled ? "bg-blue-600" : "bg-gray-300"
                }`}
                aria-pressed={isEnabled}
                aria-labelledby="toggle-label"
            >
                <span
                    className={`inline-block w-4 h-4 transform bg-white rounded-full transition-transform ${
                        isEnabled ? "translate-x-6" : "translate-x-1"
                    }`}
                />
            </button>
            <span className="ml-2 text-sm" id="toggle-label">
                {isEnabled ? "활성화" : "비활성화"}
            </span>
        </div>
    );
};

interface AgentConfigManagerProps {
    selectedAgentRole?: string; // 선택된 에이전트 역할 (선택적)
}

const AgentConfigManager: React.FC<AgentConfigManagerProps> = ({
    selectedAgentRole,
}) => {
    const [agents, setAgents] = useState<Record<string, AgentConfig>>({});
    const [loading, setLoading] = useState(true);
    const [saveStatus, setSaveStatus] = useState<Record<string, string>>({});
    const [configStatus, setConfigStatus] = useState<Record<string, string>>(
        {}
    );
    const [enablementStates, setEnablementStates] = useState<
        Record<string, boolean>
    >({});

    useEffect(() => {
        // 에이전트 목록 및 설정 파라미터 로드
        const loadAgents = async () => {
            try {
                const response = await axios.get("/api/registry/agents");
                const agentsData = response.data.agents || response.data;

                console.log("로드된 에이전트 데이터:", agentsData);

                // 로컬 스토리지에서 저장된 설정 불러오기
                const savedConfigs: Record<string, Record<string, string>> = {};

                // 기존 방식: agent_config_ 프리픽스 저장
                Object.keys(localStorage).forEach((key) => {
                    if (key.startsWith("agent_config_")) {
                        const role = key.replace("agent_config_", "");
                        try {
                            savedConfigs[role] = JSON.parse(
                                localStorage.getItem(key) || "{}"
                            );
                        } catch (e) {
                            console.error(`설정 파싱 오류 (${role}):`, e);
                        }
                    }
                });

                // 에이전트별 설정 객체 생성
                const configuredAgents: Record<string, AgentConfig> = {};
                const statuses: Record<string, string> = {};

                // 각 에이전트에 대해 설정 파라미터 확인
                for (const agent of agentsData) {
                    const role = agent.role;
                    const id = agent.id;

                    // API에서 config_params가 제공되는 경우에만 설정 가능한 에이전트로 처리
                    if (agent.config_params && agent.config_params.length > 0) {
                        configuredAgents[role] = {
                            role: role,
                            id: id,
                            config_params: agent.config_params,
                            values: savedConfigs[role] || {},
                        };

                        // 설정 상태 확인
                        const requiredParams = agent.config_params
                            .filter((param: ConfigParam) => param.required)
                            .map((param: ConfigParam) => param.name);

                        statuses[role] =
                            agentConfigService.getConfigurationStatus(
                                role,
                                requiredParams
                            );
                    }
                    // 설정이 없는 에이전트도 활성화/비활성화 설정을 위해 추가
                    else {
                        configuredAgents[role] = {
                            role: role,
                            id: id,
                            config_params: [],
                            values: {},
                        };
                    }
                }

                console.log("설정 가능한 에이전트:", configuredAgents);

                // 에이전트 활성화 상태 초기화
                agentEnablementService.initializeAgents(agentsData, true);
                setEnablementStates(
                    agentEnablementService.getAllEnablementStates()
                );

                setAgents(configuredAgents);
                setConfigStatus(statuses);
                setLoading(false);
            } catch (error) {
                console.error("에이전트 목록 로드 실패:", error);
                setLoading(false);
            }
        };

        loadAgents();
    }, []);

    // 필터링된 에이전트 목록을 가져오는 함수
    const getFilteredAgents = () => {
        if (selectedAgentRole) {
            // 선택된 에이전트만 필터링
            return Object.values(agents).filter(
                (agent) => agent.role === selectedAgentRole
            );
        }
        // 선택된 에이전트가 없으면 모든 에이전트 반환
        return Object.values(agents);
    };

    // 설정 변경 핸들러
    const handleConfigChange = (
        role: string,
        paramName: string,
        value: string
    ) => {
        setAgents((prev) => {
            const newAgents = { ...prev };
            if (!newAgents[role]) {
                newAgents[role] = { role, config_params: [], values: {} };
            }
            newAgents[role].values[paramName] = value;

            // 에이전트 서비스에 설정 저장
            agentConfigService.updateConfig(role, paramName, value);

            // 저장 상태 업데이트
            setSaveStatus({
                ...saveStatus,
                [role]: "저장됨",
            });

            // 3초 후 저장 상태 메시지 제거
            setTimeout(() => {
                setSaveStatus((prev) => {
                    const newStatus = { ...prev };
                    delete newStatus[role];
                    return newStatus;
                });
            }, 3000);

            // 설정 상태 업데이트
            const agent = newAgents[role];
            const requiredParams = agent.config_params
                .filter((param) => param.required)
                .map((param) => param.name);

            setConfigStatus((prev) => ({
                ...prev,
                [role]: agentConfigService.getConfigurationStatus(
                    role,
                    requiredParams
                ),
            }));

            return newAgents;
        });
    };

    // 활성화 상태 변경 핸들러
    const handleToggleEnable = (agentId: string) => {
        const newState = !enablementStates[agentId];

        // 활성화 상태 변경
        agentEnablementService.setEnabled(agentId, newState);

        // 상태 업데이트
        setEnablementStates({
            ...enablementStates,
            [agentId]: newState,
        });
    };

    const validateConfig = (agent: AgentConfig): boolean => {
        // 필수 파라미터가 모두 입력되었는지 확인
        return agent.config_params
            .filter((param) => param.required)
            .every(
                (param) =>
                    agent.values[param.name] &&
                    agent.values[param.name].trim() !== ""
            );
    };

    if (loading) {
        return <div className="p-4">에이전트 설정 로드 중...</div>;
    }

    // 필터링된 에이전트 목록
    const filteredAgents = getFilteredAgents();

    if (filteredAgents.length === 0) {
        return (
            <div className="p-4 text-gray-600">
                {selectedAgentRole
                    ? `'${selectedAgentRole}' 에이전트에 대한 설정이 없습니다.`
                    : "설정이 필요한 에이전트가 없습니다."}
            </div>
        );
    }

    return (
        <div
            className={
                selectedAgentRole ? "" : "p-4 bg-white shadow rounded-lg"
            }
        >
            {!selectedAgentRole && (
                <h2 className="text-xl font-bold mb-4">에이전트 설정</h2>
            )}
            {filteredAgents.map((agent) => (
                <div
                    key={agent.role}
                    className="mb-6 p-4 border border-gray-200 rounded"
                >
                    <div className="flex justify-between items-center mb-4">
                        <div className="flex items-center gap-2">
                            <h3 className="text-lg font-semibold">
                                {agent.role} 설정
                            </h3>
                            {agent.config_params.length > 0 && (
                                <StatusBadge
                                    status={
                                        configStatus[agent.role] || "not_found"
                                    }
                                />
                            )}
                        </div>
                        {saveStatus[agent.role] && (
                            <span className="text-sm text-green-600 bg-green-100 px-2 py-1 rounded">
                                {saveStatus[agent.role]}
                            </span>
                        )}
                    </div>

                    {/* 활성화/비활성화 토글 스위치 */}
                    <div className="mb-4 p-2 bg-gray-50 rounded border border-gray-200">
                        <ToggleSwitch
                            isEnabled={
                                agent.id
                                    ? enablementStates[agent.id] !== false
                                    : true
                            }
                            onChange={() =>
                                agent.id && handleToggleEnable(agent.id)
                            }
                            label="에이전트 상태:"
                        />
                    </div>

                    {agent.config_params.length > 0 ? (
                        <div>
                            <div className="text-sm font-medium mb-3">
                                설정 항목
                            </div>
                            {agent.config_params.map((param) => (
                                <div key={param.name} className="mb-3">
                                    <label
                                        htmlFor={`${agent.role}-${param.name}`}
                                        className="block text-sm font-medium text-gray-700 mb-1"
                                    >
                                        {param.description}
                                        {param.required && (
                                            <span className="text-red-500">
                                                *
                                            </span>
                                        )}
                                    </label>
                                    <input
                                        type={
                                            param.is_secret
                                                ? "password"
                                                : "text"
                                        }
                                        id={`${agent.role}-${param.name}`}
                                        value={agent.values[param.name] || ""}
                                        onChange={(e) =>
                                            handleConfigChange(
                                                agent.role,
                                                param.name,
                                                e.target.value
                                            )
                                        }
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                                        placeholder={`${param.description} 입력...`}
                                    />
                                    {param.is_secret && (
                                        <p className="text-xs text-gray-500 mt-1">
                                            보안을 위해 API 키는 로컬에만
                                            저장됩니다.
                                        </p>
                                    )}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-sm text-gray-500">
                            이 에이전트는 별도의 설정이 필요하지 않습니다.
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
};

export default AgentConfigManager;
