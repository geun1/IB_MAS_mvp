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
    getConversationStatus: async (
        conversationId: string
    ): Promise<QueryResponse> => {
        const response = await apiClient.get(
            `${BASE_URL}/conversation/${conversationId}`
        );
        return response.data;
    },

    // 서비스 상태 확인
    checkHealth: async (): Promise<any> => {
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
