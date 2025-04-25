import axios, { AxiosRequestConfig, AxiosResponse } from "axios";

// 기본 API 클라이언트 설정
const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || "", // 환경변수 추가
    timeout: 60000, // 30초 타임아웃
    headers: {
        "Content-Type": "application/json",
    },
});

// 요청 인터셉터 (필요시 인증 토큰 추가 등)
apiClient.interceptors.request.use(
    (config) => {
        // 필요한 경우 여기서 요청 설정 수정
        return config;
    },
    (error) => {
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
        console.error("API 요청 오류:", error.response?.data || error.message);
        return Promise.reject(error);
    }
);

export default apiClient;
