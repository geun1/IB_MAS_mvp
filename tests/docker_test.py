import subprocess
import time
import argparse
import logging
import os

# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("docker_test")

def run_command(command, cwd=None):
    """명령어 실행 및 출력 반환"""
    logger.info(f"명령 실행: {command}")
    result = subprocess.run(
        command, 
        shell=True, 
        capture_output=True, 
        text=True,
        cwd=cwd
    )
    return result

def wait_for_services():
    """모든 서비스가 준비될 때까지 대기"""
    logger.info("서비스 준비 대기 중...")
    
    max_attempts = 30
    attempt = 0
    services_ready = False
    
    while attempt < max_attempts and not services_ready:
        attempt += 1
        logger.info(f"서비스 상태 확인 시도 {attempt}/{max_attempts}...")
        
        # 레지스트리 서비스 확인
        registry_check = run_command("docker-compose exec -T registry curl -s http://localhost:8000/health || echo 'fail'")
        broker_check = run_command("docker-compose exec -T broker curl -s http://localhost:8000/health || echo 'fail'")
        
        if "fail" not in registry_check.stdout and "fail" not in broker_check.stdout:
            services_ready = True
            logger.info("모든 서비스가 준비되었습니다!")
        else:
            logger.info("일부 서비스가 아직 준비되지 않았습니다. 10초 대기...")
            time.sleep(10)
    
    if not services_ready:
        logger.error(f"{max_attempts}번 시도 후에도 서비스가 준비되지 않았습니다.")
        return False
        
    # 추가 대기 시간
    logger.info("안정화를 위해 10초 더 대기...")
    time.sleep(10)
    return True

def run_tests(test_type):
    """지정된 테스트 실행"""
    logger.info(f"{test_type} 테스트 실행 중...")
    
    if test_type == "all":
        # 모든 테스트 실행
        run_command("docker-compose exec broker bash -c 'cd /app/tests && python test_workflow_integration.py'")
        run_command("docker-compose exec broker bash -c 'cd /app/tests && python test_resilience.py'")
        run_command("docker-compose exec broker bash -c 'cd /app/tests && python test_concurrent_tasks.py'")
    elif test_type == "workflow":
        # 워크플로우 테스트만 실행
        run_command("docker-compose exec broker bash -c 'cd /app/tests && python test_workflow_integration.py'")
    elif test_type == "resilience":
        # 장애 복구 테스트만 실행
        run_command("docker-compose exec broker bash -c 'cd /app/tests && python test_resilience.py'")
    elif test_type == "concurrent":
        # 동시 처리 테스트만 실행
        run_command("docker-compose exec broker bash -c 'cd /app/tests && python test_concurrent_tasks.py'")
    else:
        logger.error(f"알 수 없는 테스트 유형: {test_type}")
        return False
        
    return True

def main():
    """Docker 환경에서 통합 테스트 실행"""
    parser = argparse.ArgumentParser(description="Docker 환경에서 통합 테스트 실행")
    parser.add_argument("--type", default="all", choices=["all", "workflow", "resilience", "concurrent"],
                        help="실행할 테스트 유형 (기본값: all)")
    parser.add_argument("--rebuild", action="store_true", help="테스트 전 Docker 이미지 재빌드")
    args = parser.parse_args()
    
    # 현재 디렉토리 확인
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logger.info(f"프로젝트 루트 디렉토리: {project_root}")
    
    try:
        # Docker Compose 환경 확인
        docker_check = run_command("docker-compose --version")
        if docker_check.returncode != 0:
            logger.error("Docker Compose를 찾을 수 없습니다.")
            return
            
        # 필요한 경우 이미지 재빌드
        if args.rebuild:
            logger.info("Docker 이미지 재빌드 중...")
            run_command("docker-compose build", cwd=project_root)
        
        # Docker Compose 환경 시작
        logger.info("Docker Compose 환경 시작 중...")
        run_command("docker-compose up -d", cwd=project_root)
        
        # 서비스 준비 대기
        if not wait_for_services():
            logger.error("서비스가 준비되지 않아 테스트를 중단합니다.")
            return
            
        # 테스트 실행
        run_tests(args.type)
        
        logger.info("테스트 완료!")
            
    except Exception as e:
        logger.error(f"테스트 실행 중 오류 발생: {str(e)}")
    finally:
        # 사용자 선택에 따라 환경 유지 또는 정리
        choice = input("Docker Compose 환경을 종료할까요? (y/n): ").strip().lower()
        if choice == 'y':
            logger.info("Docker Compose 환경 종료 중...")
            run_command("docker-compose down", cwd=project_root)
        else:
            logger.info("Docker Compose 환경이 계속 실행됩니다.")

if __name__ == "__main__":
    main() 