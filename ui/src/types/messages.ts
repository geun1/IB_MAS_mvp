// 메시지 타입 정의
export interface Message {
    id?: string;
    role: string;
    content: string;
    timestamp: Date;
    conversationId?: string;
    finalResult?: boolean;
    request?: string;
    response?: string;
    created_at?: number;
    updated_at?: number;
    status?: string;
}

// 대화 처리 메시지 타입
export interface ProcessMessage extends Message {
    type: "task_split" | "agent_result" | "integration";
    taskDescription?: string;
    taskIndex?: number;
    status?: string;
}

// 태스크 정보 타입
export interface TaskInfo {
    id: string;
    role: string;
    description: string;
    status: string;
    result?: any;
}

// 대화 상태 타입
export enum ConversationStatus {
    PENDING = "pending",
    PROCESSING = "processing",
    COMPLETED = "completed",
    FAILED = "failed",
}

// 대화 목록 아이템 타입
export interface ConversationListItem {
    conversation_id: string;
    status: string;
    created_at: number;
    updated_at: number;
    query: string;
    task_count: number;
    messages?: Message[];
}

// 대화 상세 정보 타입
export interface ConversationDetail {
    conversation_id: string;
    status: string;
    tasks: any[];
    message: string;
    created_at?: number;
    updated_at?: number;
    query?: string;
}
