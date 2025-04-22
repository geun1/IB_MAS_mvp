import apiClient from "./api-client";
import { Agent } from "../types";

const BASE_URL = "/api/registry";

export const registryApi = {
    // 모든 에이전트 목록 조회
    getAllAgents: async (): Promise<Agent[]> => {
        try {
            const response = await apiClient.get(`${BASE_URL}/agents`);
            if (response.data.agents) {
                // 응답 구조 확인
                return response.data.agents;
            }
            return [];
        } catch (error) {
            console.error("에이전트 목록 조회 상세 오류:", error);
            return [];
        }
    },

    // 특정 역할의 에이전트 조회
    getAgentsByRole: async (role: string): Promise<Agent[]> => {
        const response = await apiClient.get(
            `${BASE_URL}/agents/by-role/${role}`
        );
        return response.data;
    },

    // 특정 에이전트 상세 정보 조회
    getAgentDetails: async (agentId: string): Promise<Agent> => {
        const response = await apiClient.get(`${BASE_URL}/agents/${agentId}`);
        return response.data.data;
    },

    // 서비스 상태 확인
    checkHealth: async (): Promise<any> => {
        const response = await apiClient.get(`${BASE_URL}/health`);
        return response.data;
    },
};
