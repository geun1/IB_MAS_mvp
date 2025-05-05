import React, { useState } from "react";
import { BrowserRouter as Router, Routes, Route, Link } from "react-router-dom";
import Dashboard from "./components/Dashboard";
import RequestForm from "./components/RequestForm";
import TaskMonitor from "./components/TaskMonitor";
import AgentStatus from "./components/AgentStatus";
import ResultViewer from "./components/ResultViewer";
import ConversationList from "./components/ConversationList";

// 홈 페이지 컴포넌트 - 3단 레이아웃 UI로 변경
const Home: React.FC = () => {
    const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);

    // 사이드바 및 패널 열림/닫힘 상태
    const [isHistorySidebarOpen, setIsHistorySidebarOpen] =
        useState<boolean>(false);
    const [isAgentPanelOpen, setIsAgentPanelOpen] = useState<boolean>(true);

    // 사이드바/패널 토글 함수
    const toggleHistorySidebar = () =>
        setIsHistorySidebarOpen(!isHistorySidebarOpen);
    const toggleAgentPanel = () => setIsAgentPanelOpen(!isAgentPanelOpen);

    return (
        <div className="relative flex h-[calc(100vh-120px)]">
            {/* 왼쪽 대화 기록 사이드바 */}
            <div
                className={`absolute md:relative left-0 top-0 h-full bg-white z-10 shadow-lg transition-all duration-300 ${
                    isHistorySidebarOpen ? "w-80" : "w-0 md:w-12"
                } overflow-hidden`}
            >
                <div className="h-full flex flex-col">
                    {/* 사이드바 토글 버튼 */}
                    <button
                        onClick={toggleHistorySidebar}
                        className="p-2 bg-gray-100 hover:bg-gray-200 text-gray-700 w-full flex justify-center"
                    >
                        {isHistorySidebarOpen ? (
                            <span className="flex items-center">
                                <svg
                                    xmlns="http://www.w3.org/2000/svg"
                                    className="h-5 w-5 mr-2"
                                    viewBox="0 0 20 20"
                                    fill="currentColor"
                                >
                                    <path
                                        fillRule="evenodd"
                                        d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"
                                        clipRule="evenodd"
                                    />
                                </svg>
                                대화 기록 닫기
                            </span>
                        ) : (
                            <svg
                                xmlns="http://www.w3.org/2000/svg"
                                className="h-5 w-5"
                                viewBox="0 0 20 20"
                                fill="currentColor"
                            >
                                <path
                                    fillRule="evenodd"
                                    d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                                    clipRule="evenodd"
                                />
                            </svg>
                        )}
                    </button>

                    {/* 대화 기록 컴포넌트 */}
                    <div className="flex-grow overflow-auto">
                        {isHistorySidebarOpen && <ConversationList />}
                    </div>
                </div>
            </div>

            {/* 가운데 채팅 영역 - 항상 가능한 많은 공간 차지 */}
            <div
                className={`flex-grow flex flex-col transition-all duration-300 ${
                    !isHistorySidebarOpen && !isAgentPanelOpen
                        ? "mx-auto max-w-3xl"
                        : ""
                }`}
            >
                <RequestForm onTaskCreated={setCurrentTaskId} />
            </div>

            {/* 오른쪽 에이전트 상태 패널 */}
            <div
                className={`absolute md:relative right-0 top-0 h-full bg-white z-10 shadow-lg transition-all duration-300 ${
                    isAgentPanelOpen ? "w-80" : "w-0 md:w-12"
                } overflow-hidden`}
            >
                <div className="h-full flex flex-col">
                    {/* 패널 토글 버튼 */}
                    <button
                        onClick={toggleAgentPanel}
                        className="p-2 bg-gray-100 hover:bg-gray-200 text-gray-700 w-full flex justify-center"
                    >
                        {isAgentPanelOpen ? (
                            <span className="flex items-center">
                                <svg
                                    xmlns="http://www.w3.org/2000/svg"
                                    className="h-5 w-5 mr-2"
                                    viewBox="0 0 20 20"
                                    fill="currentColor"
                                >
                                    <path
                                        fillRule="evenodd"
                                        d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                                        clipRule="evenodd"
                                    />
                                </svg>
                                에이전트 상태 닫기
                            </span>
                        ) : (
                            <svg
                                xmlns="http://www.w3.org/2000/svg"
                                className="h-5 w-5"
                                viewBox="0 0 20 20"
                                fill="currentColor"
                            >
                                <path
                                    fillRule="evenodd"
                                    d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"
                                    clipRule="evenodd"
                                />
                            </svg>
                        )}
                    </button>

                    {/* 에이전트 상태 컴포넌트 */}
                    <div className="flex-grow overflow-auto">
                        {isAgentPanelOpen && <AgentStatus />}
                    </div>
                </div>
            </div>
        </div>
    );
};

const App: React.FC = () => {
    return (
        <Router>
            <div className="container mx-auto px-4 py-4 h-screen flex flex-col">
                <header className="mb-4">
                    <h1 className="text-2xl font-bold text-gray-800">
                        멀티에이전트 서비스 시스템
                    </h1>
                    <p className="text-sm text-gray-600">
                        여러 에이전트들이 협업하여 복잡한 태스크를 처리합니다.
                    </p>
                </header>

                <div className="flex-grow overflow-hidden">
                    <Routes>
                        <Route path="/" element={<Home />} />
                    </Routes>
                </div>
            </div>
        </Router>
    );
};

export default App;
