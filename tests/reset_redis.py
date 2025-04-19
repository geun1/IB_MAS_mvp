import redis
import logging
import sys
import argparse

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("redis_reset")

def reset_redis_data(host='localhost', port=6380, selective=True):
    """Redis 데이터 초기화 함수
    
    Args:
        host: Redis 호스트
        port: Redis 포트
        selective: True면 레지스트리/브로커 관련 키만 삭제, False면 전체 삭제
    """
    try:
        # Redis 연결
        r = redis.Redis(host=host, port=port, decode_responses=True)
        
        # 연결 테스트
        if not r.ping():
            logger.error(f"Redis 서버에 연결할 수 없습니다: {host}:{port}")
            return False
            
        logger.info(f"Redis 서버 연결 성공: {host}:{port}")
        
        if selective:
            # 레지스트리/브로커 관련 키만 삭제
            registry_keys = r.keys("registry:*")
            broker_keys = r.keys("broker:*")
            agent_keys = r.keys("agent:*")
            task_keys = r.keys("task:*")
            
            all_keys = registry_keys + broker_keys + agent_keys + task_keys
            
            if all_keys:
                logger.info(f"삭제할 레지스트리/브로커 관련 키: {len(all_keys)}개")
                for key in all_keys:
                    logger.debug(f"키 삭제: {key}")
                    r.delete(key)
            else:
                logger.info("삭제할 레지스트리/브로커 관련 키가 없습니다.")
                
            # 리스트 구조 확인 및 초기화
            lists_to_check = ["registry:agents", "broker:tasks"]
            for list_key in lists_to_check:
                key_type = r.type(list_key)
                logger.info(f"키 '{list_key}' 타입: {key_type}")
                
                if key_type != "none" and key_type != "list":
                    logger.warning(f"키 '{list_key}'가 리스트가 아닙니다. 삭제 후 초기화합니다.")
                    r.delete(list_key)
        else:
            # 전체 데이터베이스 삭제 (주의!)
            logger.warning("모든 Redis 데이터를 삭제합니다!")
            r.flushall()
            
        logger.info("Redis 데이터 초기화 완료!")
        return True
        
    except Exception as e:
        logger.error(f"Redis 초기화 중 오류 발생: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Redis 데이터 초기화 도구")
    parser.add_argument("--host", default="localhost", help="Redis 호스트 (기본값: localhost)")
    parser.add_argument("--port", type=int, default=6380, help="Redis 포트 (기본값: 6380)")
    parser.add_argument("--all", action="store_true", help="모든 데이터 삭제 (주의!)")
    
    args = parser.parse_args()
    
    logger.info("===== Redis 데이터 초기화 시작 =====")
    
    success = reset_redis_data(
        host=args.host,
        port=args.port,
        selective=not args.all
    )
    
    if success:
        logger.info("===== Redis 데이터 초기화 성공 =====")
        return 0
    else:
        logger.error("===== Redis 데이터 초기화 실패 =====")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 