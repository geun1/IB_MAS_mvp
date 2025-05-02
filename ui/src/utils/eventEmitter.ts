type EventCallback = (data: any) => void;

/**
 * 컴포넌트 간 통신을 위한 단순 이벤트 에미터
 */
class EventEmitter {
    private events: Record<string, EventCallback[]> = {};

    /**
     * 이벤트 구독
     * @param event 이벤트 이름
     * @param callback 이벤트 발생 시 실행할 콜백 함수
     */
    public on(event: string, callback: EventCallback): void {
        if (!this.events[event]) {
            this.events[event] = [];
        }
        this.events[event].push(callback);
    }

    /**
     * 이벤트 구독 해제
     * @param event 이벤트 이름
     * @param callback 제거할 콜백 함수
     */
    public off(event: string, callback: EventCallback): void {
        if (!this.events[event]) return;
        this.events[event] = this.events[event].filter((cb) => cb !== callback);
    }

    /**
     * 이벤트 발행
     * @param event 이벤트 이름
     * @param data 이벤트 데이터
     */
    public emit(event: string, data: any): void {
        if (!this.events[event]) return;
        this.events[event].forEach((callback) => {
            try {
                callback(data);
            } catch (error) {
                console.error(`이벤트 핸들러 실행 중 오류 (${event}):`, error);
            }
        });
    }
}

// 싱글톤 인스턴스 생성
export const eventEmitter = new EventEmitter();
