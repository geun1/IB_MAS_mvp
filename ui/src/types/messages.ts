// 기본 메시지 타입
export interface Message {
    role: "user" | "assistant" | "system";
    content: string;
    timestamp: Date;
    conversationId?: string;
    taskId?: string;
    finalResult?: boolean;
}

// 처리 과정 메시지 타입
export interface ProcessMessage extends Message {
    // 처리 단계 타입
    processType: "task_split" | "agent_processing" | "agent_result";
    // 태스크 ID (에이전트 처리 시)
    taskId?: string;
    // 에이전트 역할명
    agentRole?: string;
    // 처리 상태
    status?: "pending" | "processing" | "completed" | "failed";
    // 태스크 인덱스 (분해된 순서)
    taskIndex?: number;
    // 태스크 설명
    taskDescription?: string;
}

// 태스크 정보
export interface TaskInfo {
    id: string;
    status: string;
    description?: string;
    role?: string;
    result?: any;
    // 태스크 인덱스 (업무 분할 순서)
    index?: number;
    // 태스크 의존성 (어떤 태스크에 의존하는지)
    depends_on?: string[];
    // 태스크 레벨 (실행 순서)
    level?: number;
    // 태스크 시작 시간
    created_at?: number;
    // 태스크 완료 시간
    completed_at?: number;
}

// 대화 상태 타입
export interface ConversationStatus {
    conversation_id: string;
    status: string;
    tasks: TaskInfo[];
    message?: string;
    // 태스크 분해 결과
    taskDecomposition?: {
        original_query: string;
        tasks: Array<{
            description: string;
            role: string;
            index: number;
            level?: number;
        }>;
    };
    // 실행 레벨 (태스크 실행 순서)
    execution_levels?: number[][];
}
