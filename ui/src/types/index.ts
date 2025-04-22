// 에이전트 관련 타입
export interface Agent {
    id: string;
    role: string;
    description: string;
    status: string;
    endpoint?: string;
    params: AgentParam[];
    load: number;
    active_tasks: number;
    last_heartbeat?: string;
    metrics?: {
        memory_usage?: number;
        cpu_usage?: number;
        active_tasks?: number;
    };
}

export interface AgentParam {
    name: string;
    description: string;
    type: string;
    required: boolean;
    default?: any;
    enum?: any[];
}

// 태스크 관련 타입
export enum TaskStatus {
    PENDING = "pending",
    PROCESSING = "processing",
    COMPLETED = "completed",
    FAILED = "failed",
    CANCELLED = "cancelled",
}

export interface TaskRequest {
    role: string;
    params: Record<string, any>;
    conversation_id: string;
}

export interface TaskResponse {
    task_id: string;
    status: string;
    message: string;
    result?: Record<string, any>;
}

export interface TaskResult {
    task_id: string;
    status: TaskStatus;
    role: string;
    params: Record<string, any>;
    result: string | Record<string, any>;
    error?: string;
    agent_id?: string;
    created_at: number;
    updated_at: number;
    completed_at?: number;
    execution_time?: number;
    cache_hit: boolean;
}

export interface TaskList {
    tasks: TaskResult[];
    total: number;
    page: number;
    page_size: number;
}

// 시나리오 정의
export interface Scenario {
    id: string;
    name: string;
    description: string;
    tasks: TaskRequest[];
}

// 오케스트레이터 요청/응답 타입
export interface QueryRequest {
    query: string;
    conversation_id?: string;
    user_id?: string;
    context?: Record<string, any>;
}

export interface QueryResponse {
    conversation_id: string;
    status: string;
    tasks: Array<{
        id: string;
        status: string;
        result?: any;
    }>;
    message?: string;
}
