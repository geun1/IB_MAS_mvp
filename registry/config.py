import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# Redis 설정
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# 에이전트 설정
DEFAULT_TTL = int(os.getenv("AGENT_TTL", 30))  # 30초
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", 10))  # 10초

# 서버 설정
HOST = os.getenv("REGISTRY_HOST", "0.0.0.0")
PORT = int(os.getenv("REGISTRY_PORT", 8000)) 