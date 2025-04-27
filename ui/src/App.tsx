import React, { useState } from "react";
import { BrowserRouter as Router, Routes, Route, Link } from "react-router-dom";
import Dashboard from "./components/Dashboard";
import RequestForm from "./components/RequestForm";
import TaskMonitor from "./components/TaskMonitor";
import AgentStatus from "./components/AgentStatus";
import ResultViewer from "./components/ResultViewer";
import ConversationList from "./components/ConversationList";
import AgentSettings from "./pages/AgentSettings";

// 기존 홈 페이지 컴포넌트
const Home: React.FC = () => {
    const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<"request" | "history">(
        "request"
    );

    return (
        <div>
            {/* 탭 메뉴 */}
            <div className="mb-6 border-b">
                <div className="flex">
                    <button
                        className={`px-4 py-2 font-medium border-b-2 ${
                            activeTab === "request"
                                ? "border-blue-500 text-blue-600"
                                : "border-transparent text-gray-500 hover:text-gray-700"
                        }`}
                        onClick={() => setActiveTab("request")}
                    >
                        새 요청
                    </button>
                    <button
                        className={`px-4 py-2 font-medium border-b-2 ${
                            activeTab === "history"
                                ? "border-blue-500 text-blue-600"
                                : "border-transparent text-gray-500 hover:text-gray-700"
                        }`}
                        onClick={() => setActiveTab("history")}
                    >
                        대화 기록
                    </button>
                </div>
            </div>

            {activeTab === "request" ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div>
                        <RequestForm onTaskCreated={setCurrentTaskId} />
                        <TaskMonitor taskId={currentTaskId} className="mt-6" />
                    </div>

                    <div>
                        <ResultViewer taskId={currentTaskId} className="mb-6" />
                        <AgentStatus />
                    </div>
                </div>
            ) : (
                <ConversationList />
            )}
        </div>
    );
};

const App: React.FC = () => {
    return (
        <Router>
            <div className="container mx-auto px-4 py-8">
                <header className="mb-8">
                    <h1 className="text-3xl font-bold text-gray-800">
                        멀티에이전트 서비스 시스템
                    </h1>
                    <p className="text-gray-600">
                        여러 에이전트들이 협업하여 복잡한 태스크를 처리합니다.
                    </p>

                    {/* 네비게이션 메뉴 */}
                    <nav className="mt-4">
                        <ul className="flex space-x-4">
                            <li>
                                <Link
                                    to="/"
                                    className="text-blue-600 hover:text-blue-800"
                                >
                                    홈
                                </Link>
                            </li>
                            <li>
                                <Link
                                    to="/settings"
                                    className="text-blue-600 hover:text-blue-800"
                                >
                                    에이전트 설정
                                </Link>
                            </li>
                        </ul>
                    </nav>
                </header>

                <Routes>
                    <Route path="/" element={<Home />} />
                    <Route path="/settings" element={<AgentSettings />} />
                </Routes>
            </div>
        </Router>
    );
};

export default App;
