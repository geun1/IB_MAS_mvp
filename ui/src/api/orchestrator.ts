import apiClient from "./api-client";
import { QueryRequest, QueryResponse } from "../types";
import { agentConfigService } from "../services/AgentConfigService";
import { agentEnablementService } from "../services/AgentEnablementService";

const BASE_URL = "/api/orchestrator";

export const orchestratorApi = {
    // 질의 처리 API
    processQuery: async (request: QueryRequest): Promise<QueryResponse> => {
        try {
            const { query, conversation_id, context, message_id } = request;

            // 메시지 ID 검증
            if (!message_id) {
                console.error(
                    "[API] 쿼리 처리 실패: 메시지 ID가 누락되었습니다."
                );
                throw new Error("메시지 ID가 필요합니다.");
            }

            // 요청에 메시지 ID 포함 로그
            console.log(`[API] 요청에 메시지 ID 포함: ${message_id}`);

            // 에이전트 설정 정보 가져오기
            const agentConfigs = agentConfigService.getRequestConfigs();

            // 비활성화된 에이전트 ID 목록 가져오기
            let disabledAgentIds = agentEnablementService.getDisabledAgentIds();

            // 문자열 배열이 맞는지 확인하고 필터링
            disabledAgentIds = disabledAgentIds.filter(
                (id): id is string => typeof id === "string"
            );

            // API 요청 데이터 구성
            const requestData = {
                query,
                conversation_id,
                message_id, // 메시지 ID 포함
                context,
                agent_configs: agentConfigs,
                disabled_agents: disabledAgentIds,
            };

            // 최종 요청 데이터 로깅
            console.log("오케스트레이터 최종 요청 데이터:", requestData);

            // API 호출
            const response = await apiClient.post(
                `${BASE_URL}/query`,
                requestData
            );
            return response.data;
        } catch (error) {
            console.error("[API] 쿼리 처리 오류:", error);
            throw error;
        }
    },

    // 대화 목록 조회 API (ConversationList에서 사용 - listConversations로 별칭)
    listConversations: async () => {
        try {
            const response = await apiClient.get(`${BASE_URL}/conversations`);
            return response.data.conversations || [];
        } catch (error) {
            console.error("대화 목록 조회 오류:", error);
            throw error;
        }
    },

    // 대화 상세 정보 조회 API (ConversationList에서 사용)
    getConversationDetail: async (conversationId: string) => {
        try {
            // 대화 정보 가져오기
            const response = await apiClient.get(
                `${BASE_URL}/conversations/${conversationId}`
            );

            return response.data;
        } catch (error) {
            console.error("대화 상세 정보 조회 오류:", error);
            throw error;
        }
    },

    // 대화에 속한 메시지 목록 조회 API
    getConversationMessages: async (conversationId: string) => {
        try {
            // 대화에 속한 메시지 목록 조회
            const response = await apiClient.get(
                `${BASE_URL}/conversations/${conversationId}/messages`
            );
            return response.data.messages || [];
        } catch (error) {
            console.error("대화 메시지 목록 조회 오류:", error);
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

    // 태스크 분해 결과 조회 API
    getTaskDecomposition: async (
        conversationId: string,
        messageId: string
    ): Promise<any> => {
        if (!conversationId) {
            console.error(
                "[API] 태스크 분해 결과 조회 실패: 대화 ID가 없습니다."
            );
            throw new Error("대화 ID가 필요합니다.");
        }

        if (!messageId) {
            console.error(
                "[API] 태스크 분해 결과 조회 실패: 메시지 ID가 없습니다."
            );
            throw new Error("메시지 ID가 필요합니다.");
        }

        console.log(
            `[API] 태스크 분해 결과 요청: 대화=${conversationId}, 메시지=${messageId}`
        );

        try {
            const response = await apiClient.get(
                `${BASE_URL}/conversations/${conversationId}/decomposition?message_id=${messageId}`
            );
            return response.data;
        } catch (error) {
            console.error(`[API] 태스크 분해 결과 조회 오류:`, error);
            throw error;
        }
    },

    // 에이전트 태스크 결과 조회 API
    getAgentTasks: async (
        conversationId: string,
        messageId: string
    ): Promise<any> => {
        if (!conversationId) {
            console.error(
                "[API] 에이전트 태스크 결과 조회 실패: 대화 ID가 없습니다."
            );
            throw new Error("대화 ID가 필요합니다.");
        }

        if (!messageId) {
            console.error(
                "[API] 에이전트 태스크 결과 조회 실패: 메시지 ID가 없습니다."
            );
            throw new Error("메시지 ID가 필요합니다.");
        }

        console.log(
            `[API] 에이전트 태스크 결과 요청: 대화=${conversationId}, 메시지=${messageId}`
        );

        try {
            const response = await apiClient.get(
                `${BASE_URL}/conversations/${conversationId}/tasks?message_id=${messageId}`
            );
            return response.data;
        } catch (error) {
            console.error(`[API] 에이전트 태스크 결과 조회 오류:`, error);
            throw error;
        }
    },

    // 최종 결과 조회 API
    getFinalResult: async (
        conversationId: string,
        messageId: string
    ): Promise<any> => {
        if (!conversationId) {
            console.error("[API] 최종 결과 조회 실패: 대화 ID가 없습니다.");
            throw new Error("대화 ID가 필요합니다.");
        }

        if (!messageId) {
            console.error("[API] 최종 결과 조회 실패: 메시지 ID가 없습니다.");
            throw new Error("메시지 ID가 필요합니다.");
        }

        console.log(
            `[API] 최종 결과 요청: 대화=${conversationId}, 메시지=${messageId}`
        );

        try {
            const response = await apiClient.get(
                `${BASE_URL}/conversations/${conversationId}/result?message_id=${messageId}`
            );
            return response.data;
        } catch (error) {
            console.error(`[API] 최종 결과 조회 오류:`, error);
            throw error;
        }
    },

    // 대화 상태 조회 API
    getConversationStatus: async (conversationId: string): Promise<any> => {
        if (!conversationId) {
            console.error("[API] 대화 상태 조회 실패: 대화 ID가 없습니다.");
            throw new Error("대화 ID가 필요합니다.");
        }

        console.log(`[API] 대화 상태 요청: 대화=${conversationId}`);

        try {
            const response = await apiClient.get(
                `${BASE_URL}/conversations/${conversationId}/status`
            );
            return response.data;
        } catch (error) {
            console.error(`[API] 대화 상태 조회 오류:`, error);
            throw error;
        }
    },
};

// 고유한 대화 ID 생성 함수
function generateConversationId(): string {
    return (
        Math.random().toString(36).substring(2, 15) +
        Math.random().toString(36).substring(2, 15)
    );
}
