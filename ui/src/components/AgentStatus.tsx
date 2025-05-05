import React, { useState } from "react";
import { useQuery } from "react-query";
import { registryApi } from "../api/registry";
import { Agent } from "../types";
import AgentConfigManager from "./AgentConfigManager";
import Modal from "./Modal";

const AgentStatus: React.FC = () => {
    // 에이전트 목록 및 필터링 상태
    const [filter, setFilter] = useState<string>("all");
    const [searchTerm, setSearchTerm] = useState<string>("");

    // 설정 모달 상태
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [selectedAgentRole, setSelectedAgentRole] = useState<string>("");

    // 에이전트 목록 조회
    const {
        data: agents,
        isLoading,
        isError,
        refetch,
    } = useQuery("agents", registryApi.getAllAgents, {
        refetchInterval: 10000, // 10초마다 갱신
        staleTime: 5000,
    });

    // 상태에 따른 배지 스타일
    const getStatusBadgeStyle = (status: string) => {
        switch (status) {
            case "available":
                return "bg-green-100 text-green-800";
            case "busy":
                return "bg-yellow-100 text-yellow-800";
            case "offline":
                return "bg-red-100 text-red-800";
            default:
                return "bg-gray-100 text-gray-800";
        }
    };

    // 에이전트 상태 한글 표시
    const getStatusText = (status: string) => {
        switch (status) {
            case "available":
                return "사용 가능";
            case "busy":
                return "작업 중";
            case "offline":
                return "오프라인";
            default:
                return "알 수 없음";
        }
    };

    // 에이전트 설정 모달 열기
    const openConfigModal = (role: string) => {
        setSelectedAgentRole(role);
        setIsModalOpen(true);
    };

    // 설정 모달 닫기
    const closeConfigModal = () => {
        setIsModalOpen(false);
    };

    // 필터링된 에이전트 목록
    const getFilteredAgents = () => {
        // agents가 배열이 아닌 경우 빈 배열 반환
        if (!agents || !Array.isArray(agents)) return [];

        let filteredList = [...agents];

        // 상태별 필터링
        if (filter !== "all") {
            filteredList = filteredList.filter(
                (agent) => agent.status === filter
            );
        }

        // 검색어 필터링
        if (searchTerm) {
            const term = searchTerm.toLowerCase();
            filteredList = filteredList.filter(
                (agent) =>
                    agent.role.toLowerCase().includes(term) ||
                    agent.description.toLowerCase().includes(term) ||
                    agent.id.toLowerCase().includes(term)
            );
        }

        return filteredList;
    };

    // 로딩 중 표시
    if (isLoading) {
        return (
            <div className="bg-white rounded-lg shadow-md p-6">
                <h2 className="text-xl font-bold mb-4">에이전트 상태</h2>
                <div className="flex justify-center p-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    <span className="ml-2">에이전트 목록 로딩 중...</span>
                </div>
            </div>
        );
    }

    // 에러 표시
    if (isError) {
        return (
            <div className="bg-white rounded-lg shadow-md p-6">
                <h2 className="text-xl font-bold mb-4">에이전트 상태</h2>
                <div className="bg-red-50 text-red-600 p-4 rounded-md">
                    에이전트 목록을 불러오는 중 오류가 발생했습니다.
                    <button
                        onClick={() => refetch()}
                        className="ml-2 text-sm underline"
                    >
                        다시 시도
                    </button>
                </div>
            </div>
        );
    }

    // 필터링된 에이전트 목록
    const filteredAgents = getFilteredAgents();

    return (
        <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-bold mb-4">에이전트 상태</h2>

            {/* 필터 및 검색 UI */}
            <div className="mb-4 flex flex-wrap gap-2">
                <div className="flex flex-col flex-grow">
                    <label htmlFor="agent-search" className="text-sm mb-1">
                        에이전트 검색
                    </label>
                    <input
                        type="text"
                        id="agent-search"
                        placeholder="역할, 설명, ID로 검색..."
                        className="px-3 py-2 border rounded-md text-sm"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>
                <div className="flex flex-col">
                    <label htmlFor="status-filter" className="text-sm mb-1">
                        상태 필터
                    </label>
                    <select
                        id="status-filter"
                        className="px-3 py-2 border rounded-md bg-white text-sm"
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                    >
                        <option value="all">모든 상태</option>
                        <option value="available">사용 가능</option>
                        <option value="busy">작업 중</option>
                        <option value="offline">오프라인</option>
                    </select>
                </div>
            </div>

            {/* 에이전트 목록 */}
            {filteredAgents.length > 0 ? (
                <div className="space-y-3">
                    {filteredAgents.map((agent) => (
                        <div
                            key={agent.id}
                            className="border rounded-md p-3 hover:bg-gray-50 transition-colors"
                        >
                            <div className="flex items-start justify-between">
                                <div>
                                    <h3 className="font-medium">
                                        {agent.role}
                                        <span
                                            className={`ml-2 text-xs px-2 py-0.5 rounded-full ${getStatusBadgeStyle(
                                                agent.status
                                            )}`}
                                        >
                                            {getStatusText(agent.status)}
                                        </span>
                                    </h3>
                                    <p className="text-sm text-gray-600 mt-1">
                                        {agent.description}
                                    </p>
                                </div>

                                {/* 설정 버튼 */}
                                <button
                                    onClick={() => openConfigModal(agent.role)}
                                    className="px-3 py-1 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 transition-colors text-sm"
                                >
                                    설정
                                </button>
                            </div>

                            {/* 추가 정보 표시 */}
                            <div className="mt-2 flex flex-wrap text-xs text-gray-500 gap-x-4">
                                <div>ID: {agent.id.substring(0, 8)}...</div>
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="text-center py-8 text-gray-500">
                    {searchTerm || filter !== "all" ? (
                        <>
                            <p>조건에 맞는 에이전트가 없습니다.</p>
                            <button
                                onClick={() => {
                                    setSearchTerm("");
                                    setFilter("all");
                                }}
                                className="text-blue-500 hover:underline mt-2"
                            >
                                필터 초기화
                            </button>
                        </>
                    ) : (
                        <p>등록된 에이전트가 없습니다.</p>
                    )}
                </div>
            )}

            {/* 에이전트 설정 모달 */}
            <Modal
                isOpen={isModalOpen}
                onClose={closeConfigModal}
                title={`${selectedAgentRole} 설정`}
            >
                <AgentConfigManager selectedAgentRole={selectedAgentRole} />
            </Modal>
        </div>
    );
};

export default AgentStatus;
