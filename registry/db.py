import json
import time
import logging
from typing import List, Optional, Dict, Any
import redis
from .models import Agent, AgentStatus, AgentHeartbeat, AgentParam
from .config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, DEFAULT_TTL

class RedisClient:
    def __init__(self):
        self.redis = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
    async def register_agent(self, agent: Agent) -> bool:
        """에이전트 등록 또는 업데이트"""
        try:
            # JSON으로 직렬화할 수 있도록 에이전트 객체를 딕셔너리로 변환
            agent_data = agent.dict()
            
            # Redis에 에이전트 정보 저장
            self.redis.hset("agents", agent.id, json.dumps(agent_data))
            
            # 역할별 에이전트 목록에 추가
            self.redis.sadd(f"role:{agent.role}", agent.id)
            self.redis.sadd("roles", agent.role)
            self.redis.sadd("agents", agent.id)
            
            # 에이전트 TTL 설정 (기본 30초)
            self.redis.set(f"ttl:{agent.id}", int(time.time()), ex=DEFAULT_TTL)
            
            # 파라미터 스키마 저장
            if agent.params:
                param_schema = [param.dict() for param in agent.params]
                self.redis.hset("agent_params", agent.id, json.dumps(param_schema))
            
            return True
        except Exception as e:
            logging.error(f"에이전트 등록 오류: {str(e)}")
            return False
    
    async def update_heartbeat(self, heartbeat: AgentHeartbeat, ttl: int = DEFAULT_TTL) -> bool:
        """에이전트 상태 업데이트 및 TTL 갱신"""
        try:
            agent_key = f"agent:{heartbeat.role}:{heartbeat.agent_id}"
            
            # 현재 에이전트 데이터 가져오기
            agent_data = self.redis.get(agent_key)
            if not agent_data:
                return False  # 에이전트 없음
                
            agent = Agent.model_validate_json(agent_data)
            
            # 상태가 변경되었으면 상태 인덱스 업데이트
            if agent.status != heartbeat.status:
                pipeline = self.redis.pipeline()
                pipeline.srem(f"status:{agent.status}", agent.id)
                pipeline.sadd(f"status:{heartbeat.status}", agent.id)
                pipeline.execute()
            
            # 에이전트 정보 업데이트
            agent.status = heartbeat.status
            agent.load = heartbeat.load
            agent.active_tasks = heartbeat.active_tasks
            agent.last_heartbeat = float(self.redis.time()[0])  # Redis 서버 시간 사용
            agent.error_message = heartbeat.error_message
            
            # 업데이트된 정보 저장 및 TTL 갱신
            self.redis.set(agent_key, agent.model_dump_json(), ex=ttl)
            return True
            
        except Exception as e:
            print(f"Heartbeat 업데이트 실패: {str(e)}")
            return False
    
    async def get_agent(self, agent_id: str) -> Optional[Agent]:
        """에이전트 정보 조회"""
        try:
            agent_data = self.redis.hget("agents", agent_id)
            if agent_data:
                agent_dict = json.loads(agent_data)
                
                # 파라미터 스키마 로드
                param_data = self.redis.hget("agent_params", agent_id)
                if param_data:
                    param_list = json.loads(param_data)
                    agent_dict["params"] = [AgentParam(**param) for param in param_list]
                
                return Agent(**agent_dict)
            return None
        except Exception as e:
            logging.error(f"에이전트 조회 오류: {str(e)}")
            return None
    
    async def list_agents(self, role: Optional[str] = None, status: Optional[AgentStatus] = None) -> List[Agent]:
        """에이전트 목록 조회"""
        agents = []
        try:
            agent_ids = []
            
            # 조건에 따른 에이전트 ID 필터링
            if role and status:
                # 역할과 상태 모두 필터링
                role_agents = self.redis.smembers(f"role:{role}")
                status_agents = self.redis.smembers(f"status:{status}")
                agent_ids = list(role_agents.intersection(status_agents))
            elif role:
                # 역할만 필터링
                agent_ids = self.redis.smembers(f"role:{role}")
            elif status:
                # 상태만 필터링
                agent_ids = self.redis.smembers(f"status:{status}")
            else:
                # 모든 에이전트
                agent_ids = self.redis.smembers("agents")
            
            # 에이전트 정보 조회
            for agent_id in agent_ids:
                # 역할 찾기
                agent_role = None
                for r in self.redis.smembers("roles"):
                    if self.redis.sismember(f"role:{r}", agent_id):
                        agent_role = r
                        break
                
                if agent_role:
                    agent_key = f"agent:{agent_role}:{agent_id}"
                    agent_data = self.redis.get(agent_key)
                    if agent_data:
                        agents.append(Agent.model_validate_json(agent_data))
            
            return agents
        except Exception as e:
            print(f"에이전트 목록 조회 실패: {str(e)}")
            return []
    
    async def unregister_agent(self, role: str, agent_id: str) -> bool:
        """에이전트 등록 해제"""
        try:
            agent_key = f"agent:{role}:{agent_id}"
            
            # 현재 에이전트 정보 조회
            agent_data = self.redis.get(agent_key)
            if not agent_data:
                return False  # 이미 없는 에이전트
                
            agent = Agent.model_validate_json(agent_data)
            
            # Redis 트랜잭션으로 모든 인덱스에서 제거
            pipeline = self.redis.pipeline()
            pipeline.delete(agent_key)
            pipeline.srem(f"role:{role}", agent_id)
            pipeline.srem(f"status:{agent.status}", agent_id)
            pipeline.srem("agents", agent_id)
            
            # 해당 역할의 에이전트가 더 이상 없으면 역할도 제거
            if not self.redis.scard(f"role:{role}"):
                pipeline.srem("roles", role)
                
            pipeline.execute()
            return True
        except Exception as e:
            print(f"에이전트 제거 실패: {str(e)}")
            return False
    
    async def cleanup_inactive_agents(self, cutoff_time: float) -> int:
        """비활성 에이전트 정리 (TTL만료 외에 추가적인 정리)"""
        count = 0
        try:
            # 모든 에이전트 및 역할 조회
            roles = self.redis.smembers("roles")
            
            for role in roles:
                agent_ids = self.redis.smembers(f"role:{role}")
                
                for agent_id in agent_ids:
                    agent_key = f"agent:{role}:{agent_id}"
                    agent_data = self.redis.get(agent_key)
                    
                    # TTL이 만료되어 데이터가 없거나, 마지막 하트비트가 cutoff_time보다 오래된 경우
                    if not agent_data:
                        # 인덱스에서만 제거 (데이터는 이미 TTL로 제거됨)
                        pipeline = self.redis.pipeline()
                        pipeline.srem(f"role:{role}", agent_id)
                        pipeline.srem("agents", agent_id)
                        pipeline.execute()
                        count += 1
                    else:
                        agent = Agent.model_validate_json(agent_data)
                        if agent.last_heartbeat and agent.last_heartbeat < cutoff_time:
                            # 인덱스 및 데이터 모두 제거
                            await self.unregister_agent(role, agent_id)
                            count += 1
            
            return count
        except Exception as e:
            print(f"비활성 에이전트 정리 실패: {str(e)}")
            return 0

    async def update_agent_statistics(self, agent_id: str, task_status: str, execution_time: Optional[float] = None):
        """에이전트 태스크 통계 업데이트"""
        try:
            # 현재 통계 조회
            stats_key = f"agent_stats:{agent_id}"
            stats_data = self.redis.get(stats_key)
            
            if stats_data:
                stats = json.loads(stats_data)
            else:
                stats = {
                    "total_tasks": 0,
                    "completed_tasks": 0,
                    "failed_tasks": 0,
                    "success_rate": 0.0,
                    "avg_execution_time": 0.0,
                    "last_task_time": time.time()
                }
            
            # 통계 업데이트
            stats["total_tasks"] += 1
            stats["last_task_time"] = time.time()
            
            if task_status == "completed":
                stats["completed_tasks"] += 1
                if execution_time:
                    # 가중 평균으로 실행 시간 업데이트
                    if stats["avg_execution_time"] > 0:
                        stats["avg_execution_time"] = 0.8 * stats["avg_execution_time"] + 0.2 * execution_time
                    else:
                        stats["avg_execution_time"] = execution_time
            elif task_status == "failed":
                stats["failed_tasks"] += 1
            
            # 성공률 계산
            if stats["total_tasks"] > 0:
                stats["success_rate"] = stats["completed_tasks"] / stats["total_tasks"]
            
            # 통계 저장
            self.redis.set(stats_key, json.dumps(stats))
            return True
        except Exception as e:
            logging.error(f"에이전트 통계 업데이트 오류: {str(e)}")
            return False

    async def get_agents_by_role(self, role: str, status: Optional[str] = None, max_load: float = 1.0) -> List[Agent]:
        """특정 역할의 사용 가능한 에이전트 목록 조회"""
        try:
            # 기존 list_agents 메소드를 활용
            agents = await self.list_agents(role, status)
            
            # max_load 기준으로 필터링
            if max_load < 1.0:
                agents = [agent for agent in agents if agent.load <= max_load]
            
            return agents
        except Exception as e:
            logging.error(f"역할별 에이전트 조회 오류: {str(e)}")
            return []

# 싱글톤 인스턴스
redis_client = RedisClient() 