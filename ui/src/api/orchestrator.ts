import apiClient from "./api-client";
import { QueryRequest, QueryResponse } from "../types";
import { agentConfigService } from "../services/AgentConfigService";
import { agentEnablementService } from "../services/AgentEnablementService";

const BASE_URL = "/api/orchestrator";

export const orchestratorApi = {
    // 질의 처리 API
    processQuery: async (request: QueryRequest): Promise<QueryResponse> => {
        try {
            const { query, conversation_id, context } = request;

            // 에이전트 설정 정보 가져오기
            const agentConfigs = agentConfigService.getRequestConfigs();

            // 비활성화된 에이전트 ID 목록 가져오기
            let disabledAgentIds = agentEnablementService.getDisabledAgentIds();

            // 문자열 배열이 맞는지 확인하고 필터링
            disabledAgentIds = disabledAgentIds
                .filter((id) => id !== null && id !== undefined)
                .map((id) => String(id));

            // 요청 데이터 생성
            const requestData: QueryRequest = {
                query,
                conversation_id,
                agent_configs: agentConfigs,
            };

            // 비활성화된 에이전트가 있는 경우에만 추가
            if (disabledAgentIds && disabledAgentIds.length > 0) {
                requestData.disabled_agents = disabledAgentIds;
            }

            // 컨텍스트가 있으면 추가
            if (context) {
                requestData.context = context;
            }

            // 요청 데이터 최종 확인 로그
            console.log(
                "오케스트레이터 최종 요청 데이터:",
                JSON.stringify(requestData, null, 2)
            );

            // API 요청 실행
            const response = await apiClient.post(
                `${BASE_URL}/query`,
                requestData
            );
            return response.data;
        } catch (error: any) {
            console.error("오케스트레이터 API 오류:", error);
            throw error;
        }
    },

    // 대화 목록 조회 API
    getConversations: async () => {
        try {
            const response = await apiClient.get(`${BASE_URL}/conversations`);
            return response.data;
        } catch (error) {
            console.error("대화 목록 조회 오류:", error);
            throw error;
        }
    },

    // 대화 내역 조회 API
    getConversation: async (conversationId: string) => {
        try {
            const response = await apiClient.get(
                `${BASE_URL}/conversations/${conversationId}`
            );
            return response.data;
        } catch (error) {
            console.error("대화 내역 조회 오류:", error);
            throw error;
        }
    },

    // 대화 삭제 API
    deleteConversation: async (conversationId: string) => {
        try {
            const response = await apiClient.delete(
                `${BASE_URL}/conversations/${conversationId}`
            );
            return response.data;
        } catch (error) {
            console.error("대화 삭제 오류:", error);
            throw error;
        }
    },

    // 서비스 상태 확인
    checkHealth: async () => {
        const response = await apiClient.get(`${BASE_URL}/health`);
        return response.data;
    },
};

// 고유한 대화 ID 생성 함수
function generateConversationId(): string {
    return (
        Math.random().toString(36).substring(2, 15) +
        Math.random().toString(36).substring(2, 15)
    );
}
