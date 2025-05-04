import apiClient from "./api-client";
import { TaskRequest, TaskResponse, TaskResult, TaskList } from "../types";
import { agentConfigService } from "../services/AgentConfigService";
import { agentEnablementService } from "../services/AgentEnablementService";

const BASE_URL = "/api/broker";

export const brokerApi = {
    // 태스크 생성 API
    createTask: async (role: string, params: any, conversationId: string) => {
        try {
            // 문자열 확인
            role = String(role);
            conversationId = String(conversationId);

            // 에이전트 설정 가져오기 (각 역할별 설정 값)
            const agentConfigs = agentConfigService.getRequestConfigs();

            // 에이전트 활성화 상태 확인 (역할 기준)
            // 역할에 해당하는 ID들 중 하나라도 활성화되어 있는지 확인
            const isRoleEnabled = agentEnablementService.isRoleEnabled(role);
            if (!isRoleEnabled) {
                throw new Error(
                    `에이전트 "${role}"은(는) 비활성화 상태입니다.`
                );
            }

            // API 요청 데이터 구성
            const requestData = {
                role,
                params,
                conversation_id: conversationId,
                agent_configs: agentConfigs,
                // 사용할 에이전트 제한 정보는 없음 - 현재 역할의 에이전트만 사용함
            };

            console.log("태스크 생성 요청:", JSON.stringify(requestData));

            // 태스크 생성 요청
            const response = await apiClient.post(
                `${BASE_URL}/tasks`,
                requestData
            );
            return response.data;
        } catch (error: any) {
            console.error("태스크 생성 오류:", error);
            throw error;
        }
    },

    // 태스크 조회 API
    getTask: async (taskId: string) => {
        taskId = String(taskId);
        const response = await apiClient.get(`${BASE_URL}/tasks/${taskId}`);
        return response.data;
    },

    // 대화 ID로 태스크 목록 조회
    getTasksByConversation: async (conversationId: string) => {
        conversationId = String(conversationId);
        const response = await apiClient.get(
            `${BASE_URL}/tasks/by-conversation/${conversationId}`
        );
        return response.data;
    },

    // 직접 태스크 실행 (ReACT 에이전트 등에서 필요)
    executeTask: async (
        taskId: string,
        role: string,
        params: any,
        excludeAgent?: string
    ) => {
        // 문자열 확인
        taskId = String(taskId);
        role = String(role);
        if (excludeAgent) excludeAgent = String(excludeAgent);

        // 에이전트 활성화 상태 확인 (역할 기준)
        const isRoleEnabled = agentEnablementService.isRoleEnabled(role);
        if (!isRoleEnabled) {
            throw new Error(`에이전트 "${role}"은(는) 비활성화 상태입니다.`);
        }

        const requestData = {
            task_id: taskId,
            role,
            params,
            exclude_agent: excludeAgent,
        };

        console.log("태스크 실행 요청:", JSON.stringify(requestData));

        const response = await apiClient.post(
            `${BASE_URL}/execute_task`,
            requestData
        );
        return response.data;
    },

    // 태스크 취소 API
    cancelTask: async (taskId: string) => {
        taskId = String(taskId);
        const response = await apiClient.post(
            `${BASE_URL}/tasks/${taskId}/cancel`
        );
        return response.data;
    },

    // 태스크 목록 조회
    listTasks: async (
        page: number = 1,
        pageSize: number = 20,
        status?: string,
        role?: string
    ): Promise<TaskList> => {
        const params: any = {
            page,
            page_size: pageSize,
        };

        if (status) params.status = String(status);
        if (role) params.role = String(role);

        const response = await apiClient.get(`${BASE_URL}/tasks`, { params });
        return response.data;
    },

    // 서비스 상태 확인
    checkHealth: async (): Promise<any> => {
        const response = await apiClient.get(`${BASE_URL}/health`);
        return response.data;
    },
};
