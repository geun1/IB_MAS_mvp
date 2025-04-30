import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "react-query";
import App from "./App";
import "./index.css";
import { agentConfigService } from "./services/AgentConfigService";

// 에이전트 설정 서비스 초기화 (앱 시작 시 로컬 스토리지에서 데이터 로드)
agentConfigService;

// 쿼리 클라이언트 설정
const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            refetchOnWindowFocus: false,
            retry: 1,
            staleTime: 180000, // 1분
        },
    },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
        <QueryClientProvider client={queryClient}>
            <App />
        </QueryClientProvider>
    </React.StrictMode>
);
