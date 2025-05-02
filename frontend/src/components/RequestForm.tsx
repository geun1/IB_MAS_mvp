function extractMessage(result: any): string {
    console.log("결과 구조 확인:", result);

    // 결과가 없는 경우
    if (!result) {
        console.log("결과가 없습니다");
        return "처리가 완료되었으나 결과가 없습니다.";
    }

    // 결과가 단순 문자열인 경우
    if (typeof result === "string") {
        console.log("결과가 문자열입니다");
        return result;
    }

    // 결과가 이미 포맷팅된 경우 - 백엔드에서 result.result.content를 직접 반환하는 경우
    if (typeof result === "string") {
        console.log("결과가 포맷팅된 문자열입니다");
        return result;
    }

    // 보통 백엔드에서 format_conversation_result에서 처리된 결과가 옴
    try {
        if (typeof result === "object") {
            // 일반적인 패턴: result에 바로 접근
            if (result.message) {
                console.log("result.message 패턴 감지");
                return result.message;
            }

            // 중첩 패턴: result.result.content
            if (result.result && result.result.content) {
                console.log("result.result.content 패턴 감지");
                return result.result.content;
            }

            // 중첩 패턴: result.result.message
            if (result.result && result.result.message) {
                console.log("result.result.message 패턴 감지");
                return result.result.message;
            }

            // 중첩 패턴: result.content
            if (result.content) {
                console.log("result.content 패턴 감지");
                return result.content;
            }

            // 결과가 있지만 예상 구조가 아닌 경우
            console.log("예상치 못한 결과 구조:", result);
            if (JSON.stringify(result).length > 0) {
                return JSON.stringify(result, null, 2);
            }
        }
    } catch (error) {
        console.error("결과 추출 중 오류:", error);
    }

    return "처리가 완료되었으나 표시할 결과가 없습니다.";
}
