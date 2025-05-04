import React, { useState, useEffect } from "react";
import { useQuery } from "react-query";
import { registryApi } from "../api/registry";
import { Agent } from "../types";
import { agentEnablementService } from "../services/AgentEnablementService";

const AgentEnablementManager: React.FC = () => {
    // 에이전트 상태 저장
    const [agentStates, setAgentStates] = useState<Record<string, boolean>>({});
    const [searchTerm, setSearchTerm] = useState<string>("");

    // 레지스트리에서 에이전트 목록 조회
    const {
        data: agents,
        isLoading,
        isError,
        refetch,
    } = useQuery("agents", registryApi.getAllAgents, {
        staleTime: 10000, // 10초 동안 데이터 유지
    });

    // 에이전트 목록이 로드되면 활성화 상태 초기화
    useEffect(() => {
        if (agents && agents.length > 0) {
            // 에이전트 목록으로 초기화 (역할과 ID 매핑 포함)
            agentEnablementService.initializeAgents(agents, true);

            // 최신 상태 업데이트
            setAgentStates(agentEnablementService.getAllEnablementStates());
        }
    }, [agents]);

    // 에이전트 활성화 상태 변경 핸들러
    const handleToggleAgent = (agentId: string) => {
        const newState = !agentStates[agentId];
        agentEnablementService.setEnabled(agentId, newState);

        setAgentStates({
            ...agentStates,
            [agentId]: newState,
        });
    };

    // 검색어 처리
    const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setSearchTerm(e.target.value.toLowerCase());
    };

    // 검색 결과 필터링
    const filteredAgents = agents?.filter(
        (agent) =>
            agent.role.toLowerCase().includes(searchTerm) ||
            agent.description.toLowerCase().includes(searchTerm)
    );

    if (isLoading) {
        return <div className="p-4">에이전트 목록 로딩 중...</div>;
    }

    if (isError) {
        return (
            <div className="p-4 text-red-500">
                에이전트 목록을 불러오는 중 오류가 발생했습니다.
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="mb-6">
                <input
                    type="text"
                    placeholder="에이전트 검색..."
                    className="w-full p-2 border rounded"
                    onChange={handleSearchChange}
                    value={searchTerm}
                />
            </div>

            <div className="space-y-2">
                {filteredAgents?.map((agent) => (
                    <div
                        key={agent.id}
                        className="flex items-center justify-between p-4 border rounded hover:bg-gray-50"
                    >
                        <div className="flex-1">
                            <div className="font-semibold">{agent.role}</div>
                            <div className="text-sm text-gray-600">
                                {agent.description}
                            </div>
                            <div className="text-xs text-gray-400 mt-1">
                                ID: {agent.id}
                            </div>
                        </div>
                        <div className="ml-4">
                            <button
                                onClick={() => handleToggleAgent(agent.id)}
                                className={`px-3 py-1 rounded transition-colors ${
                                    agentStates[agent.id] !== false
                                        ? "bg-green-500 text-white"
                                        : "bg-red-500 text-white"
                                }`}
                            >
                                {agentStates[agent.id] !== false
                                    ? "활성화됨"
                                    : "비활성화됨"}
                            </button>
                        </div>
                    </div>
                ))}
                {filteredAgents?.length === 0 && (
                    <div className="p-4 text-center text-gray-500">
                        검색 결과가 없습니다.
                    </div>
                )}
            </div>
        </div>
    );
};

export default AgentEnablementManager;
