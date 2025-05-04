/**
 * AgentEnablementService - 에이전트 활성화/비활성화 상태 관리 서비스
 *
 * 이 서비스는 레지스트리에 등록된 에이전트 중 유저가 실제로 사용하고자 하는
 * 에이전트들을 선택적으로 활성화/비활성화할 수 있게 합니다.
 */

class AgentEnablementService {
    // 스토리지 키
    private readonly STORAGE_KEY = "agent_enablement";

    // 에이전트 활성화 상태 맵 (id -> boolean)
    private enablementMap: Record<string, boolean> = {};

    // ID와 역할 매핑 정보
    private idToRoleMap: Record<string, string> = {};
    private roleToIdMap: Record<string, string[]> = {};

    constructor() {
        this.loadFromStorage();
    }

    /**
     * 로컬 스토리지에서 활성화 상태 로드
     */
    private loadFromStorage() {
        try {
            const storedData = localStorage.getItem(this.STORAGE_KEY);
            if (storedData) {
                const parsed = JSON.parse(storedData);
                this.enablementMap = parsed.enablementMap || {};
                this.idToRoleMap = parsed.idToRoleMap || {};
                this.roleToIdMap = parsed.roleToIdMap || {};
            }
        } catch (e) {
            console.error("활성화 상태 로드 오류:", e);
            // 오류 시 기본값으로 초기화
            this.enablementMap = {};
            this.idToRoleMap = {};
            this.roleToIdMap = {};
        }
    }

    /**
     * 로컬 스토리지에 활성화 상태 저장
     */
    private saveToStorage() {
        try {
            const data = {
                enablementMap: this.enablementMap,
                idToRoleMap: this.idToRoleMap,
                roleToIdMap: this.roleToIdMap,
            };
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(data));
        } catch (e) {
            console.error("활성화 상태 저장 오류:", e);
        }
    }

    /**
     * 에이전트 활성화 여부 확인
     * @param agentId 에이전트 ID
     * @returns 활성화 여부 (기본값: true)
     */
    isEnabled(agentId: string): boolean {
        // 기본적으로 모든 에이전트는 활성화 상태 (맵에 없으면 활성화됨)
        return this.enablementMap[agentId] !== false;
    }

    /**
     * 역할별 에이전트 활성화 여부 확인
     * @param role 에이전트 역할
     * @returns 활성화 여부 (기본값: true)
     */
    isRoleEnabled(role: string): boolean {
        // 해당 역할의 모든 에이전트 ID 가져오기
        const agentIds = this.roleToIdMap[role] || [];
        // 하나라도 활성화되어 있으면 true 반환
        return (
            agentIds.length === 0 || agentIds.some((id) => this.isEnabled(id))
        );
    }

    /**
     * 에이전트 활성화 상태 설정
     * @param agentId 에이전트 ID
     * @param enabled 활성화 여부
     */
    setEnabled(agentId: string, enabled: boolean) {
        this.enablementMap[agentId] = enabled;
        this.saveToStorage();
    }

    /**
     * 역할별 활성화 상태 설정 (해당 역할의 모든 에이전트)
     * @param role 에이전트 역할
     * @param enabled 활성화 여부
     */
    setRoleEnabled(role: string, enabled: boolean) {
        const agentIds = this.roleToIdMap[role] || [];
        agentIds.forEach((id) => {
            this.enablementMap[id] = enabled;
        });
        this.saveToStorage();
    }

    /**
     * 활성화된 에이전트 ID 목록 반환
     * @returns 활성화된 에이전트 ID 배열
     */
    getEnabledAgentIds(): string[] {
        return Object.entries(this.enablementMap)
            .filter(([_, enabled]) => enabled !== false)
            .map(([id]) => String(id));
    }

    /**
     * 비활성화된 에이전트 ID 목록 반환
     * @returns 비활성화된 에이전트 ID 배열
     */
    getDisabledAgentIds(): string[] {
        return Object.entries(this.enablementMap)
            .filter(([_, enabled]) => enabled === false)
            .map(([id]) => String(id));
    }

    /**
     * 비활성화된 에이전트 ID 목록 반환
     * 오케스트레이터 API 호환을 위한 메서드
     * @returns 비활성화된 에이전트 ID 배열
     */
    getDisabledAgentRoles(): string[] {
        // 백엔드 호환을 위해 ID 목록 반환
        return this.getDisabledAgentIds();
    }

    /**
     * 활성화된 역할 목록 반환
     * @returns 활성화된 역할 배열
     */
    getEnabledRoles(): string[] {
        const roles = Object.keys(this.roleToIdMap);
        return roles.filter((role) => this.isRoleEnabled(role));
    }

    /**
     * 비활성화된 역할 목록 반환
     * @returns 비활성화된 역할 배열
     */
    getDisabledRoles(): string[] {
        const roles = Object.keys(this.roleToIdMap);
        return roles.filter((role) => !this.isRoleEnabled(role));
    }

    /**
     * 모든 에이전트 활성화 상태 맵 반환
     * @returns 에이전트 활성화 상태 맵
     */
    getAllEnablementStates(): Record<string, boolean> {
        return { ...this.enablementMap };
    }

    /**
     * 여러 에이전트의 활성화 상태를 한번에 설정
     * @param stateMap 에이전트 활성화 상태 맵
     */
    setMultipleStates(stateMap: Record<string, boolean>) {
        this.enablementMap = { ...this.enablementMap, ...stateMap };
        this.saveToStorage();
    }

    /**
     * 에이전트 목록에서 ID와 역할 매핑 정보 갱신
     * @param agents 에이전트 목록
     */
    updateAgentMapping(agents: any[]) {
        const newIdToRoleMap: Record<string, string> = {};
        const newRoleToIdMap: Record<string, string[]> = {};

        agents.forEach((agent) => {
            const { id, role } = agent;

            // ID -> 역할 매핑
            newIdToRoleMap[String(id)] = String(role);

            // 역할 -> ID 매핑 (배열)
            if (!newRoleToIdMap[role]) {
                newRoleToIdMap[role] = [];
            }
            newRoleToIdMap[role].push(String(id));
        });

        this.idToRoleMap = newIdToRoleMap;
        this.roleToIdMap = newRoleToIdMap;
        this.saveToStorage();
    }

    /**
     * 모든 에이전트 초기화 (새로 등록된 에이전트의 경우)
     * @param agents 전체 에이전트 목록
     * @param defaultState 기본 활성화 상태 (기본값: true)
     */
    initializeAgents(agents: any[], defaultState: boolean = true) {
        const newMap: Record<string, boolean> = {};

        // ID와 역할 매핑 정보 갱신
        this.updateAgentMapping(agents);

        // 기존 설정 유지하면서 새 에이전트는 기본값으로 설정
        agents.forEach((agent) => {
            const id = String(agent.id);
            if (this.enablementMap[id] === undefined) {
                newMap[id] = defaultState;
            } else {
                newMap[id] = this.enablementMap[id];
            }
        });

        this.enablementMap = newMap;
        this.saveToStorage();
    }
}

// 싱글톤 인스턴스 생성
export const agentEnablementService = new AgentEnablementService();
