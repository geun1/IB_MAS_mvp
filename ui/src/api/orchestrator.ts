import apiClient from "./api-client";
import { QueryRequest, QueryResponse } from "../types";

const BASE_URL = "/api/orchestrator";

export const orchestratorApi = {
    // 쿼리 처리 요청
    processQuery: async (request: QueryRequest): Promise<QueryResponse> => {
        const response = await apiClient.post(`${BASE_URL}/query`, request);
        return response.data;
    },

    // 대화 상태 조회
    getConversationStatus: async (conversationId: string): Promise<any> => {
        try {
            const response = await apiClient.get(
                `${BASE_URL}/conversations/${conversationId}`
            );

            // 응답 구조 로깅 (디버깅 용도)
            console.debug("대화 상태 응답:", response.data);

            return response.data;
        } catch (error) {
            console.error("대화 상태 조회 오류:", error);
            throw error;
        }
    },

    // 서비스 상태 확인
    checkHealth: async (): Promise<any> => {
        const response = await apiClient.get(`${BASE_URL}/health`);
        return response.data;
    },

    // 대화 목록 조회
    listConversations: async (): Promise<any[]> => {
        try {
            const response = await apiClient.get(`${BASE_URL}/conversations`);
            return response.data.conversations || [];
        } catch (error) {
            console.error("대화 목록 조회 중 오류:", error);
            return [];
        }
    },

    // 대화 상세 정보 조회
    getConversationDetail: async (conversationId: string): Promise<any> => {
        try {
            const response = await apiClient.get(
                `${BASE_URL}/conversations/${conversationId}/detail`
            );
            return response.data;
        } catch (error) {
            console.error(
                `대화 상세 정보 조회 중 오류 (ID: ${conversationId}):`,
                error
            );
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
