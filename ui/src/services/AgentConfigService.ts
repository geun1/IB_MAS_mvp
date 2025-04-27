class AgentConfigService {
    private configs: Record<string, Record<string, string>> = {};

    constructor() {
        this.loadFromStorage();
    }

    private loadFromStorage() {
        try {
            // 기존 단일 키 방식 로드 (이전 버전 호환성)
            const savedConfigs = localStorage.getItem("agent_configs");
            if (savedConfigs) {
                this.configs = JSON.parse(savedConfigs);

                // 기존 설정을 새 형식으로 마이그레이션
                Object.entries(this.configs).forEach(([role, config]) => {
                    localStorage.setItem(
                        `agent_config_${role}`,
                        JSON.stringify(config)
                    );
                });

                // 기존 키 삭제 (마이그레이션 완료)
                localStorage.removeItem("agent_configs");
            }

            // 에이전트별 키 방식 로드
            Object.keys(localStorage).forEach((key) => {
                if (key.startsWith("agent_config_")) {
                    const role = key.replace("agent_config_", "");
                    try {
                        this.configs[role] = JSON.parse(
                            localStorage.getItem(key) || "{}"
                        );
                    } catch (e) {
                        console.error(`설정 파싱 오류 (${role}):`, e);
                    }
                }
            });

            console.log("에이전트 설정 로드 완료:", this.configs);
        } catch (e) {
            console.error("설정 로드 실패:", e);
        }
    }

    private saveRoleConfig(role: string, config: Record<string, string>) {
        localStorage.setItem(`agent_config_${role}`, JSON.stringify(config));
    }

    getConfig(role: string): Record<string, string> {
        return this.configs[role] || {};
    }

    getAllConfigs(): Record<string, Record<string, string>> {
        return this.configs;
    }

    setConfig(role: string, config: Record<string, string>) {
        this.configs[role] = config;
        this.saveRoleConfig(role, config);
    }

    updateConfig(role: string, key: string, value: string) {
        if (!this.configs[role]) {
            this.configs[role] = {};
        }
        this.configs[role][key] = value;
        this.saveRoleConfig(role, this.configs[role]);
    }

    clearConfig(role: string) {
        delete this.configs[role];
        localStorage.removeItem(`agent_config_${role}`);
    }

    // 요청에 포함될 에이전트 설정 반환
    getRequestConfigs(): Record<string, Record<string, string>> {
        // 빈 설정이 없는 유효한 설정만 반환
        const validConfigs: Record<string, Record<string, string>> = {};

        Object.entries(this.configs).forEach(([role, config]) => {
            // 빈 객체가 아닌 경우에만 포함
            if (Object.keys(config).length > 0) {
                validConfigs[role] = config;
            }
        });

        return validConfigs;
    }

    // 특정 에이전트에 대한 필수 설정이 모두 있는지 확인
    validateConfig(role: string, requiredParams: string[]): boolean {
        const config = this.getConfig(role);
        return requiredParams.every(
            (param) => config[param] && config[param].trim() !== ""
        );
    }

    // 에이전트가 모든 필수 설정을 가지고 있는지 확인
    hasRequiredConfig(role: string, requiredParams: string[]): boolean {
        return this.validateConfig(role, requiredParams);
    }

    // 특정 에이전트의 상태 확인 (설정 완료 여부)
    getConfigurationStatus(
        role: string,
        requiredParams: string[]
    ): "configured" | "incomplete" | "not_found" {
        if (!this.configs[role]) {
            return "not_found";
        }

        return this.validateConfig(role, requiredParams)
            ? "configured"
            : "incomplete";
    }
}

export const agentConfigService = new AgentConfigService();
