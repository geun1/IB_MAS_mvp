/**
 * LLMConfigService - LLM 모델 선택 및 설정 관리를 위한 서비스
 */

export interface LLMConfig {
    componentName: string; // 컴포넌트 이름 (orchestrator, broker, specific_agent 등)
    modelName: string; // 선택된 모델 이름
    temperature?: number; // 온도 설정 (선택적)
    maxTokens?: number; // 최대 토큰 수 (선택적)
}

export const AVAILABLE_LLM_MODELS = [
    {
        id: "gpt-3.5-turbo",
        name: "GPT-3.5 Turbo",
        provider: "OpenAI",
        description: "OpenAI의 GPT-3.5 Turbo 모델",
    },
    {
        id: "gpt-4",
        name: "GPT-4",
        provider: "OpenAI",
        description: "OpenAI의 GPT-4 모델",
    },
    {
        id: "gpt-4o-mini",
        name: "GPT-4o Mini",
        provider: "OpenAI",
        description: "OpenAI의 GPT-4o Mini 모델",
    },
    {
        id: "claude-3-5-sonnet-20240620",
        name: "Claude 3 Sonnet",
        provider: "Anthropic",
        description: "Anthropic의 Claude 3 Sonnet 모델",
    },
    {
        id: "claude-3-opus-20240229",
        name: "Claude 3 Opus",
        provider: "Anthropic",
        description: "Anthropic의 Claude 3 Opus 모델",
    },
    {
        id: "claude-3-haiku-20240307",
        name: "Claude 3 Haiku",
        provider: "Anthropic",
        description: "Anthropic의 Claude 3 Haiku 모델",
    },
    {
        id: "ollama/llama3:latest",
        name: "Llama 3",
        provider: "Ollama",
        description: "Ollama의 Llama 3 모델",
    },
    {
        id: "ollama/mistral:latest",
        name: "Mistral",
        provider: "Ollama",
        description: "Ollama의 Mistral 모델",
    },
];

class LLMConfigService {
    private readonly STORAGE_KEY = "llm_config";
    private configs: Record<string, LLMConfig> = {};

    // 기본 컴포넌트 목록
    private readonly DEFAULT_COMPONENTS = [
        {
            id: "orchestrator",
            name: "오케스트레이터",
            description: "태스크 분해 및 결과 통합 담당",
        },
        {
            id: "broker",
            name: "브로커",
            description: "에이전트 간 통신 및 파라미터 관리",
        },
    ];

    constructor() {
        this.loadFromStorage();
    }

    private loadFromStorage() {
        try {
            const savedData = localStorage.getItem(this.STORAGE_KEY);
            if (savedData) {
                this.configs = JSON.parse(savedData);
                console.log("LLM 설정 로드 완료:", this.configs);
            } else {
                // 기본 설정 초기화
                this.initializeDefaultConfigs();
            }
        } catch (e) {
            console.error("LLM 설정 로드 실패:", e);
            this.initializeDefaultConfigs();
        }
    }

    private saveToStorage() {
        try {
            localStorage.setItem(
                this.STORAGE_KEY,
                JSON.stringify(this.configs)
            );
        } catch (e) {
            console.error("LLM 설정 저장 실패:", e);
        }
    }

    private initializeDefaultConfigs() {
        // 기본 컴포넌트에 대한 기본 설정 초기화
        this.DEFAULT_COMPONENTS.forEach((component) => {
            this.configs[component.id] = {
                componentName: component.id,
                modelName: "gpt-4o-mini", // 기본 모델
                temperature: 0.7,
                maxTokens: 1024,
            };
        });
        this.saveToStorage();
    }

    getConfig(componentName: string): LLMConfig | null {
        return this.configs[componentName] || null;
    }

    getAllConfigs(): Record<string, LLMConfig> {
        return { ...this.configs };
    }

    setConfig(componentName: string, config: LLMConfig) {
        this.configs[componentName] = { ...config };
        this.saveToStorage();
    }

    updateConfig(componentName: string, updates: Partial<LLMConfig>) {
        if (!this.configs[componentName]) {
            this.configs[componentName] = {
                componentName,
                modelName: "gpt-4o-mini", // 기본값
                ...updates,
            };
        } else {
            this.configs[componentName] = {
                ...this.configs[componentName],
                ...updates,
            };
        }
        this.saveToStorage();
    }

    removeConfig(componentName: string) {
        if (this.configs[componentName]) {
            delete this.configs[componentName];
            this.saveToStorage();
        }
    }

    // 컴포넌트 목록 반환 (기본 컴포넌트 + 등록된 에이전트)
    getComponents(): { id: string; name: string; description: string }[] {
        const result = [...this.DEFAULT_COMPONENTS];

        // 설정에 있는 추가 컴포넌트도 포함 (에이전트 등)
        Object.keys(this.configs)
            .filter((key) => !this.DEFAULT_COMPONENTS.some((c) => c.id === key))
            .forEach((key) => {
                result.push({
                    id: key,
                    name: key
                        .replace(/_/g, " ")
                        .replace(/\b\w/g, (l) => l.toUpperCase()),
                    description: `${key} 에이전트`,
                });
            });

        return result;
    }
}

export const llmConfigService = new LLMConfigService();
