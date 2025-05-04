import React, { useState } from "react";
import AgentConfigManager from "../components/AgentConfigManager";
import AgentEnablementManager from "../components/AgentEnablementManager";

const AgentSettings: React.FC = () => {
    const [activeTab, setActiveTab] = useState<"config" | "enablement">(
        "config"
    );

    return (
        <div className="container mx-auto px-4 py-8">
            <h1 className="text-2xl font-bold mb-6">에이전트 설정</h1>

            {/* 탭 메뉴 */}
            <div className="mb-6 border-b">
                <div className="flex">
                    <button
                        className={`px-4 py-2 font-medium border-b-2 ${
                            activeTab === "config"
                                ? "border-blue-500 text-blue-600"
                                : "border-transparent text-gray-500 hover:text-gray-700"
                        }`}
                        onClick={() => setActiveTab("config")}
                    >
                        에이전트 설정
                    </button>
                    <button
                        className={`px-4 py-2 font-medium border-b-2 ${
                            activeTab === "enablement"
                                ? "border-blue-500 text-blue-600"
                                : "border-transparent text-gray-500 hover:text-gray-700"
                        }`}
                        onClick={() => setActiveTab("enablement")}
                    >
                        에이전트 활성화 관리
                    </button>
                </div>
            </div>

            {/* 탭 컨텐츠 */}
            {activeTab === "config" ? (
                <>
                    <p className="mb-8 text-gray-600">
                        각 에이전트가 필요로 하는 API 키와 설정을 관리합니다. 이
                        설정들은 로컬 스토리지에 저장되며 태스크 요청 시
                        자동으로 포함됩니다.
                    </p>
                    <AgentConfigManager />
                </>
            ) : (
                <>
                    <p className="mb-8 text-gray-600">
                        대화에서 사용할 에이전트를 활성화하거나 비활성화합니다.
                        비활성화된 에이전트는 레지스트리에 등록되어 있더라도
                        대화에서 사용되지 않습니다.
                    </p>
                    <AgentEnablementManager />
                </>
            )}
        </div>
    );
};

export default AgentSettings;
