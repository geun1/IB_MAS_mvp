import React from "react";
import AgentConfigManager from "../components/AgentConfigManager";

const AgentSettings: React.FC = () => {
    return (
        <div className="container mx-auto px-4 py-8">
            <h1 className="text-2xl font-bold mb-6">에이전트 설정</h1>
            <p className="mb-8 text-gray-600">
                각 에이전트가 필요로 하는 API 키와 설정을 관리합니다. 이
                설정들은 로컬 스토리지에 저장되며 태스크 요청 시 자동으로
                포함됩니다.
            </p>
            <AgentConfigManager />
        </div>
    );
};

export default AgentSettings;
