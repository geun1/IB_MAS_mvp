import React, { useState } from "react";
import { BrowserRouter as Router, Routes, Route, Link } from "react-router-dom";
import Dashboard from "./components/Dashboard";
import RequestForm from "./components/RequestForm";
import TaskMonitor from "./components/TaskMonitor";
import AgentStatus from "./components/AgentStatus";
import ResultViewer from "./components/ResultViewer";
import ConversationList from "./components/ConversationList";
import LLMConfigManager from "./components/LLMConfigManager";

// 홈 페이지 컴포넌트 - 3단 레이아웃 UI로 변경
const Home: React.FC = () => {
    const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);

    // 사이드바 및 패널 열림/닫힘 상태
    const [isHistorySidebarOpen, setIsHistorySidebarOpen] =
        useState<boolean>(false);
    const [isAgentPanelOpen, setIsAgentPanelOpen] = useState<boolean>(true);
    const [isLLMPanelOpen, setIsLLMPanelOpen] = useState<boolean>(false);

    // 사이드바/패널 토글 함수
    const toggleHistorySidebar = () =>
        setIsHistorySidebarOpen(!isHistorySidebarOpen);
    const toggleAgentPanel = () => setIsAgentPanelOpen(!isAgentPanelOpen);
    const toggleLLMPanel = () => setIsLLMPanelOpen(!isLLMPanelOpen);

    return (
        <div className="relative flex h-[calc(100vh-120px)]">
            {/* 가운데 채팅 영역 - 항상 가능한 많은 공간 차지 */}
            <div
                className={`flex-1 flex flex-col ${
                    isHistorySidebarOpen ? "ml-64" : ""
                }`}
            >
                {/* 메인 요청 폼 */}
                <div className="flex-1 overflow-auto">
                    <RequestForm onTaskCreated={setCurrentTaskId} />
                </div>

                {/* 태스크 결과 뷰어 */}
                {currentTaskId && (
                    <div className="h-2/3 border-t border-gray-200">
                        <ResultViewer taskId={currentTaskId} />
                    </div>
                )}
            </div>

            {/* 오른쪽 에이전트 패널 */}
            <div
                className={`absolute right-0 top-0 h-full bg-gray-50 border-l border-gray-200 transition-all duration-300 ${
                    isAgentPanelOpen ? "w-96" : "w-0 overflow-hidden"
                }`}
            >
                <div className="flex justify-between items-center p-4 border-b border-gray-200">
                    <h3 className="font-medium">에이전트 상태</h3>
                    <button onClick={toggleAgentPanel}>
                        <svg
                            className="w-5 h-5 text-gray-500"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M6 18L18 6M6 6l12 12"
                            />
                        </svg>
                    </button>
                </div>
                <div className="p-4 overflow-auto h-[calc(100%-4rem)]">
                    <AgentStatus />
                </div>
            </div>

            {/* LLM 설정 패널 - 새로 추가 */}
            <div
                className={`absolute right-0 top-0 h-full bg-gray-50 border-l border-gray-200 transition-all duration-300 ${
                    isLLMPanelOpen ? "w-96" : "w-0 overflow-hidden"
                }`}
            >
                <div className="flex justify-between items-center p-4 border-b border-gray-200">
                    <h3 className="font-medium">LLM 모델 설정</h3>
                    <button onClick={toggleLLMPanel}>
                        <svg
                            className="w-5 h-5 text-gray-500"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M6 18L18 6M6 6l12 12"
                            />
                        </svg>
                    </button>
                </div>
                <div className="p-4 overflow-auto h-[calc(100%-4rem)]">
                    <LLMConfigManager />
                </div>
            </div>

            {/* 왼쪽 대화 기록 사이드바 */}
            <div
                className={`fixed left-0 top-0 h-full bg-gray-50 border-r border-gray-200 transition-all duration-300 ${
                    isHistorySidebarOpen ? "w-64" : "w-0 overflow-hidden"
                }`}
            >
                <div className="p-4">
                    <ConversationList />
                </div>
            </div>

            {/* 하단 제어 버튼들 */}
            <div className="fixed bottom-0 left-0 right-0 flex justify-center p-2 bg-white border-t border-gray-200">
                <div className="flex space-x-2">
                    <button
                        onClick={toggleHistorySidebar}
                        className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded text-sm"
                    >
                        {isHistorySidebarOpen ? "기록 숨기기" : "기록 보기"}
                    </button>
                    <button
                        onClick={toggleAgentPanel}
                        className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded text-sm"
                    >
                        {isAgentPanelOpen ? "에이전트 숨기기" : "에이전트 보기"}
                    </button>
                    <button
                        onClick={toggleLLMPanel}
                        className="px-4 py-2 bg-blue-100 hover:bg-blue-200 rounded text-sm"
                    >
                        {isLLMPanelOpen ? "LLM 설정 숨기기" : "LLM 설정"}
                    </button>
                </div>
            </div>
        </div>
    );
};

const App: React.FC = () => {
    return (
        <Router>
            <div className="min-h-screen bg-gray-50">
                <header className="bg-white border-b border-gray-200 px-4 py-3">
                    <h1 className="text-2xl font-semibold text-gray-800">
                        다중 에이전트 시스템
                    </h1>
                    <p className="text-sm text-gray-600">
                        여러 에이전트들이 협업하여 복잡한 태스크를 처리합니다.
                    </p>
                </header>

                <div className="flex-grow overflow-hidden">
                    <Routes>
                        <Route path="/" element={<Home />} />
                        <Route
                            path="/llm-config"
                            element={<LLMConfigManager />}
                        />
                    </Routes>
                </div>
            </div>
        </Router>
    );
};

export default App;
