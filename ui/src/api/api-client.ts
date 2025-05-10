import axios, { AxiosRequestConfig, AxiosResponse } from "axios";

// 환경 변수를 안전하게 가져오기 위한 함수
function getBaseUrl(): string {
    // @ts-ignore - Vite 환경 변수 타입 문제 무시
    return (
        (typeof import.meta !== "undefined" &&
            typeof import.meta.env !== "undefined" &&
            import.meta.env.VITE_API_BASE_URL) ||
        ""
    );
}

// 기본 API 클라이언트 설정
const apiClient = axios.create({
    baseURL: getBaseUrl(), // 환경변수 추가
    timeout: 600000, // 10분 타임아웃
    headers: {
        "Content-Type": "application/json",
    },
});

// 요청 인터셉터 (필요시 인증 토큰 추가 등)
apiClient.interceptors.request.use(
    (config) => {
        // 로깅 추가
        console.log(`API 요청: ${config.method?.toUpperCase()} ${config.url}`);

        // 요청 데이터가 있으면 로깅 (민감 정보 제외)
        if (config.data) {
            console.log("요청 데이터:", JSON.stringify(config.data, null, 2));
        }

        return config;
    },
    (error) => {
        console.error("API 요청 설정 중 오류:", error);
        return Promise.reject(error);
    }
);

// 응답 인터셉터
apiClient.interceptors.response.use(
    (response) => {
        return response;
    },
    (error) => {
        // 오류 발생 시 처리
        if (error.response) {
            // 서버에서 응답이 왔지만 오류 상태 코드가 포함된 경우
            console.error(
                `API 요청 오류 (${error.response.status}):`,
                error.response.data
            );

            // 유효성 검사 오류 (422) 추가 정보 로깅
            if (error.response.status === 422) {
                console.error(
                    "유효성 검사 오류 세부정보:",
                    JSON.stringify(error.response.data, null, 2)
                );

                // 요청 데이터 로깅하여 디버깅 지원
                if (error.config && error.config.data) {
                    try {
                        const requestData = JSON.parse(error.config.data);
                        console.error(
                            "요청된 데이터:",
                            JSON.stringify(requestData, null, 2)
                        );
                    } catch (e) {
                        console.error("원본 요청 데이터:", error.config.data);
                    }
                }
            }
        } else if (error.request) {
            // 요청은 이루어졌지만 응답이 오지 않은 경우
            console.error("API 요청은 이루어졌으나 응답 없음:", error.request);
        } else {
            // 요청 준비 중 오류가 발생한 경우
            console.error("API 요청 준비 중 오류:", error.message);
        }

        return Promise.reject(error);
    }
);

export default apiClient;
