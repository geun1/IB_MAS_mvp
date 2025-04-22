import apiClient from "./api-client";
import { TaskRequest, TaskResponse, TaskResult, TaskList } from "../types";

const BASE_URL = "/api/broker";

export const brokerApi = {
    // 태스크 직접 제출
    submitTask: async (task: TaskRequest): Promise<TaskResponse> => {
        const response = await apiClient.post(`${BASE_URL}/tasks`, task);
        return response.data;
    },

    // 특정 태스크 상태 및 결과 조회
    getTask: async (taskId: string): Promise<TaskResult> => {
        const response = await apiClient.get(`${BASE_URL}/tasks/${taskId}`);
        return response.data;
    },

    // 태스크 목록 조회
    listTasks: async (
        page: number = 1,
        pageSize: number = 20,
        status?: string,
        role?: string
    ): Promise<TaskList> => {
        const params = { page, page_size: pageSize, status, role };
        const response = await apiClient.get(`${BASE_URL}/tasks`, { params });
        return response.data;
    },

    // 태스크 취소
    cancelTask: async (
        taskId: string
    ): Promise<{ status: string; message: string }> => {
        const response = await apiClient.post(
            `${BASE_URL}/tasks/${taskId}/cancel`
        );
        return response.data;
    },

    // 서비스 상태 확인
    checkHealth: async (): Promise<any> => {
        const response = await apiClient.get(`${BASE_URL}/health`);
        return response.data;
    },

    // 대화 ID로 태스크 목록 조회
    getTasksByConversation: async (
        conversationId: string,
        page: number = 1,
        pageSize: number = 20
    ): Promise<TaskList> => {
        const response = await apiClient.get(
            `${BASE_URL}/tasks/by-conversation/${conversationId}`,
            { params: { page, page_size: pageSize } }
        );
        return response.data;
    },
};
