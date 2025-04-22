import React, { useState, useEffect } from "react";
import { useQuery } from "react-query";
import { registryApi } from "../api/registry";
import { brokerApi } from "../api/broker";
import { Agent, TaskStatus } from "../types";

const Dashboard: React.FC = () => {
    // 서비스 상태 정보 조회
    const { data: registryHealth, isLoading: isLoadingRegistry } = useQuery(
        "registryHealth",
        registryApi.checkHealth,
        { refetchInterval: 30000 } // 30초마다 갱신
    );

    const { data: brokerHealth, isLoading: isLoadingBroker } = useQuery(
        "brokerHealth",
        brokerApi.checkHealth,
        { refetchInterval: 30000 }
    );

    // 에이전트 목록 조회
    const { data: agents, isLoading: isLoadingAgents } = useQuery(
        "agents",
        registryApi.getAllAgents,
        { refetchInterval: 10000 } // 10초마다 갱신
    );

    // 태스크 목록 조회
    const { data: tasks, isLoading: isLoadingTasks } = useQuery(
        ["tasks", 1, 5],
        () => brokerApi.listTasks(1, 5),
        { refetchInterval: 5000 } // 5초마다 갱신
    );

    // 시스템 상태 계산
    const getSystemStatus = () => {
        if (isLoadingRegistry || isLoadingBroker) return "로딩 중...";

        const registryStatus = registryHealth?.status === "healthy";
        const brokerStatus = brokerHealth?.status === "healthy";

        if (registryStatus && brokerStatus) return "정상";
        if (!registryStatus && !brokerStatus) return "오프라인";
        return "일부 서비스 오류";
    };

    // 활성 에이전트 수 계산
    const getActiveAgentCount = () => {
        if (isLoadingAgents || !agents) return "로딩 중...";
        return agents.filter((agent: Agent) => agent.status === "available")
            .length;
    };

    // 진행 중인 태스크 수 계산
    const getActiveTaskCount = () => {
        if (isLoadingTasks || !tasks) return "로딩 중...";
        return tasks.tasks.filter(
            (task) =>
                task.status === TaskStatus.PROCESSING ||
                task.status === TaskStatus.PENDING
        ).length;
    };

    return (
        <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-bold mb-4">시스템 대시보드</h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* 시스템 상태 카드 */}
                <div className="bg-blue-50 p-4 rounded-md">
                    <h3 className="font-semibold text-blue-800">시스템 상태</h3>
                    <div className="mt-2 text-2xl font-bold">
                        {getSystemStatus()}
                    </div>
                </div>

                {/* 활성 에이전트 카드 */}
                <div className="bg-green-50 p-4 rounded-md">
                    <h3 className="font-semibold text-green-800">
                        활성 에이전트
                    </h3>
                    <div className="mt-2 text-2xl font-bold">
                        {getActiveAgentCount()}
                    </div>
                </div>

                {/* 진행 중인 태스크 카드 */}
                <div className="bg-purple-50 p-4 rounded-md">
                    <h3 className="font-semibold text-purple-800">
                        진행 중인 태스크
                    </h3>
                    <div className="mt-2 text-2xl font-bold">
                        {getActiveTaskCount()}
                    </div>
                </div>
            </div>

            {/* 최근 태스크 리스트 */}
            <div className="mt-6">
                <h3 className="font-semibold mb-2">최근 태스크</h3>
                {isLoadingTasks ? (
                    <p>로딩 중...</p>
                ) : tasks && tasks.tasks.length > 0 ? (
                    <ul className="divide-y">
                        {tasks.tasks.map((task) => (
                            <li key={task.task_id} className="py-2">
                                <div className="flex items-center">
                                    <span
                                        className={`inline-block w-3 h-3 rounded-full mr-2 ${
                                            task.status === TaskStatus.COMPLETED
                                                ? "bg-green-500"
                                                : task.status ===
                                                  TaskStatus.FAILED
                                                ? "bg-red-500"
                                                : task.status ===
                                                  TaskStatus.PROCESSING
                                                ? "bg-blue-500"
                                                : "bg-gray-500"
                                        }`}
                                    ></span>
                                    <span className="font-medium">
                                        {task.role}
                                    </span>
                                    <span className="ml-2 text-sm text-gray-500">
                                        {new Date(
                                            task.created_at * 1000
                                        ).toLocaleString()}
                                    </span>
                                    <span className="ml-auto text-sm">
                                        {task.status}
                                    </span>
                                </div>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="text-gray-500">최근 태스크가 없습니다.</p>
                )}
            </div>
        </div>
    );
};

export default Dashboard;
