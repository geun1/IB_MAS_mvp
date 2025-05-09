import axios from "axios";
import { LLMConfig } from "../services/LLMConfigService";

export const llmConfigApi = {
    /**
     * LLM 설정 업데이트
     */
    async updateConfig(component: string, config: LLMConfig) {
        try {
            const response = await axios.post("/api/settings/llm-config", {
                component,
                config,
            });
            return response.data;
        } catch (error) {
            console.error("LLM 설정 업데이트 중 오류:", error);
            throw error;
        }
    },

    /**
     * 특정 컴포넌트의 LLM 설정 조회
     */
    async getComponentConfig(component: string) {
        try {
            const response = await axios.get("/api/settings/llm-config", {
                params: { component },
            });
            return response.data;
        } catch (error) {
            console.error(`${component} LLM 설정 조회 중 오류:`, error);
            throw error;
        }
    },

    /**
     * 모든 컴포넌트의 LLM 설정 조회
     */
    async getAllConfigs() {
        try {
            const response = await axios.get("/api/settings/llm-config");
            return response.data.configs || {};
        } catch (error) {
            console.error("LLM 설정 조회 중 오류:", error);
            throw error;
        }
    },

    /**
     * 사용 가능한 LLM 모델 목록 조회
     */
    async getAvailableModels() {
        try {
            const response = await axios.get(
                "/api/settings/available-llm-models"
            );
            return response.data.models || [];
        } catch (error) {
            console.error("LLM 모델 목록 조회 중 오류:", error);
            throw error;
        }
    },

    /**
     * 브로커 LLM 상태 조회
     */
    async getBrokerLLMStatus() {
        try {
            const response = await axios.get("/api/settings/llm-status");
            return response.data;
        } catch (error) {
            console.error("브로커 LLM 상태 조회 중 오류:", error);
            throw error;
        }
    },

    /**
     * LLM 모델 연결 테스트
     */
    async testLLMConnection(
        modelName: string,
        component: string = "orchestrator"
    ) {
        try {
            // 오케스트레이터나 브로커 중 하나를 선택해 테스트 요청
            const endpoint =
                component === "broker"
                    ? "/api/broker/settings/test-llm-connection/"
                    : "/api/settings/test-llm-connection/";

            const response = await axios.get(`${endpoint}${modelName}`);
            return response.data;
        } catch (error: any) {
            console.error(`LLM 모델 ${modelName} 연결 테스트 중 오류:`, error);
            // 오류도 결과로 반환하여 UI에서 처리할 수 있게 함
            return {
                success: false,
                model: modelName,
                error: error.message || "알 수 없는 오류",
                message: `LLM 모델 ${modelName} 연결 테스트 실패`,
            };
        }
    },
};
