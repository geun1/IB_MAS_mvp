import json
import time
import logging
from typing import List, Optional, Dict, Any
import redis
from .models import Agent, AgentStatus, AgentHeartbeat, AgentParam
from .config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, DEFAULT_TTL

# --- 메모리 폴백용 자료구조 -----------------------------
_MEM_AGENTS: dict[str, dict] = {}
_MEM_AGENT_PARAMS: dict[str, list] = {}
# ------------------------------------------------------

class RedisClient:
    def __init__(self):
        """Redis 클라이언트 초기화"""
        try:
            self.redis = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True
            )
            # 연결 시험
            self.redis.ping()
            logging.info(f"Redis 연결 성공: {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            logging.warning(f"Redis 연결 실패, 메모리 모드로 전환: {str(e)}")
            self.redis = None       # 폴백

    async def register_agent(self, agent: Agent) -> bool:
        """에이전트 등록"""
        try:
            logging.info(f"에이전트 등록 시작: {agent.id}")
            
            # Redis가 없으면 메모리 저장
            if self.redis is None:
                _MEM_AGENTS[agent.id] = agent.model_dump()
                logging.info(f"(메모리) 에이전트 {agent.id} 등록 완료")
                return True

            try:
                # 파이프라인으로 모든 작업 수행
                pipeline = self.redis.pipeline()
                
                # 에이전트 데이터 저장
                agent_dict = agent.model_dump()
                agent_json = json.dumps(agent_dict)
                
                # 1. 에이전트 기본 정보 저장
                pipeline.hset("agents", agent.id, agent_json)
                
                # 2. 역할별 인덱스 업데이트
                pipeline.sadd(f"role:{agent.role}", agent.id)
                pipeline.sadd("roles", agent.role)
                
                # 3. 전체 에이전트 ID 목록 업데이트
                pipeline.sadd("agent_ids", agent.id)
                
                # 4. TTL 설정
                pipeline.set(f"ttl:{agent.id}", int(time.time()), ex=DEFAULT_TTL)
                
                # 파이프라인 실행
                pipeline.execute()
                
                logging.info(f"에이전트 {agent.id} 등록 완료")
                return True
                
            except redis.RedisError as e:
                logging.error(f"Redis 오류: {str(e)}")
                return False
                
        except Exception as e:
            logging.error(f"에이전트 등록 중 오류 발생: {str(e)}")
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
            # 메모리 모드
            if self.redis is None:
                for agent_dict in _MEM_AGENTS.values():
                    if role and agent_dict["role"] != role:
                        continue
                    if status and agent_dict.get("status") != status:
                        continue
                    agents.append(Agent(**agent_dict))
                return agents

            # Redis 모드
            try:
                # 1. agent_ids에서 모든 에이전트 ID 가져오기
                if role:
                    # 특정 역할의 에이전트만 가져오기
                    agent_ids = self.redis.smembers(f"role:{role}")
                    logging.info(f"Role {role} 에이전트 ID 목록: {agent_ids}")
                else:
                    # 모든 에이전트 가져오기
                    agent_ids = self.redis.smembers("agent_ids")
                    logging.info(f"전체 에이전트 ID 목록: {agent_ids}")

                # 2. 각 에이전트의 상세 정보 가져오기
                for agent_id in agent_ids:
                    agent_data = self.redis.hget("agents", agent_id)
                    if agent_data:
                        try:
                            agent_dict = json.loads(agent_data)
                            logging.info(f"에이전트 데이터 로드: {agent_id} = {agent_dict}")
                            
                            # 상태 필터링
                            if status and agent_dict.get("status") != status:
                                continue
                                
                            agents.append(Agent(**agent_dict))
                            logging.info(f"에이전트 추가됨: {agent_id}")
                        except Exception as e:
                            logging.error(f"에이전트 데이터 파싱 오류: {agent_id} - {str(e)}")

                logging.info(f"조회된 전체 에이전트 수: {len(agents)}")
                return agents
                
            except redis.RedisError as e:
                logging.error(f"Redis 조회 오류: {str(e)}")
                return []
                
        except Exception as e:
            logging.error(f"에이전트 목록 조회 실패: {str(e)}")
            return []
    
    async def unregister_agent(self, role: str, agent_id: str) -> bool:
        """에이전트 등록 해제"""
        try:
            # 로깅 추가
            logging.info(f"에이전트 등록 해제 시도: role={role}, id={agent_id}")
            
            # 해시에서 에이전트 정보 조회
            agent_data = self.redis.hget("agents", agent_id)
            if not agent_data:
                logging.warning(f"에이전트 정보 없음: {agent_id}")
                return False  # 이미 없는 에이전트
            
            # Redis 트랜잭션으로 모든 인덱스에서 제거
            pipeline = self.redis.pipeline()
            pipeline.hdel("agents", agent_id)  # 해시에서 삭제
            pipeline.srem(f"role:{role}", agent_id)  # 역할별 인덱스에서 삭제
            pipeline.srem("agent_ids", agent_id)  # ID 목록에서 삭제
            pipeline.delete(f"ttl:{agent_id}")  # TTL 키 삭제
            
            result = pipeline.execute()
            logging.info(f"등록 해제 결과: {result}")
            return True
        except Exception as e:
            logging.error(f"에이전트 제거 실패: {str(e)}")
            return False
    
    async def cleanup_inactive_agents(self, cutoff_time: float) -> int:
        """비활성 에이전트 정리"""
        try:
            if self.redis is None:
                return 0
            
            cleaned = 0
            pipeline = self.redis.pipeline()
            
            # agent_ids 집합에서 모든 에이전트 ID 가져오기
            agent_ids = self.redis.smembers("agent_ids")
            
            for agent_id in agent_ids:
                ttl_key = f"ttl:{agent_id}"
                last_heartbeat = self.redis.get(ttl_key)
                
                if last_heartbeat and float(last_heartbeat) < cutoff_time:
                    # 에이전트 정보 가져오기
                    agent_data = self.redis.hget("agents", agent_id)
                    if agent_data:
                        agent_dict = json.loads(agent_data)
                        role = agent_dict.get("role")
                        
                        # 관련된 모든 키 삭제
                        pipeline.hdel("agents", agent_id)
                        pipeline.srem("agent_ids", agent_id)
                        if role:
                            pipeline.srem(f"role:{role}", agent_id)
                        pipeline.delete(ttl_key)
                        cleaned += 1
            
            if cleaned > 0:
                pipeline.execute()
            
            return cleaned
            
        except Exception as e:
            logging.error(f"비활성 에이전트 정리 실패: {str(e)}")
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

# RedisClient 인스턴스 생성
redis_client = RedisClient() 