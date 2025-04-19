import httpx
import asyncio
import json
from pprint import pprint
import time

async def test_task_lifecycle():
    """태스크 생명주기 테스트"""
    broker_url = "http://localhost:8001"  # 브로커 서비스 URL
    
    # 1. 태스크 생성
    task_request = {
        "role": "writer",
        "params": {
            "topic": "인공지능의 미래"
        },
        "conversation_id": f"test_{int(time.time())}"
    }
    
    async with httpx.AsyncClient() as client:
        # 태스크 생성
        print("\n=== 태스크 생성 ===")
        response = await client.post(f"{broker_url}/task", json=task_request)
        if response.status_code == 200:
            result = response.json()
            task_id = result["task_id"]
            print(f"태스크 ID: {task_id}")
            print(f"상태: {result['status']}")
        else:
            print(f"오류: {response.status_code} - {response.text}")
            return
            
        # 태스크 상태 조회 (처리 중)
        print("\n=== 태스크 상태 조회 (처리 중) ===")
        await asyncio.sleep(1)  # 약간의 대기
        response = await client.get(f"{broker_url}/tasks/{task_id}")
        if response.status_code == 200:
            task_info = response.json()
            print(f"상태: {task_info['status']}")
            pprint(task_info)
        else:
            print(f"오류: {response.status_code} - {response.text}")
            
        # 태스크 완료될 때까지 대기
        print("\n=== 태스크 완료 대기 중... ===")
        completed = False
        max_wait = 30  # 최대 30초 대기
        start_time = time.time()
        
        while not completed and time.time() - start_time < max_wait:
            await asyncio.sleep(2)  # 2초마다 확인
            response = await client.get(f"{broker_url}/tasks/{task_id}")
            if response.status_code == 200:
                task_info = response.json()
                status = task_info["status"]
                print(f"현재 상태: {status}")
                
                if status in ["completed", "failed", "cancelled"]:
                    completed = True
                    print("\n=== 최종 태스크 정보 ===")
                    pprint(task_info)
            else:
                print(f"오류: {response.status_code} - {response.text}")
                break
        
        if not completed:
            print("태스크가 시간 내에 완료되지 않았습니다.")
        
        # 태스크 목록 조회
        print("\n=== 태스크 목록 조회 ===")
        response = await client.get(f"{broker_url}/tasks?role=writer&page=1&page_size=5")
        if response.status_code == 200:
            task_list = response.json()
            print(f"총 태스크 수: {task_list['total']}")
            print("최근 태스크 목록:")
            for task in task_list["tasks"]:
                print(f"- {task['task_id']}: {task['status']} ({task['role']})")
        else:
            print(f"오류: {response.status_code} - {response.text}")

if __name__ == "__main__":
    asyncio.run(test_task_lifecycle()) 