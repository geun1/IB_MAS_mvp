import httpx
import asyncio
import json
from pprint import pprint

async def test_param_inference():
    """파라미터 추론 테스트"""
    broker_url = "http://localhost:8001"  # 브로커 서비스 URL
    
    # 테스트 1: 문서 작성 태스크 (작성 주제만 제공)
    writer_test = {
        "task_description": "마케팅 전략에 대한 보고서를 작성해주세요",
        "param_schemas": [
            {
                "name": "topic",
                "description": "작성할 문서의 주제",
                "type": "string",
                "required": True
            },
            {
                "name": "tone",
                "description": "문서의 어조",
                "type": "string",
                "required": True,
                "enum": ["formal", "casual", "technical", "neutral"]
            },
            {
                "name": "length",
                "description": "문서 길이(단어 수)",
                "type": "number",
                "required": True,
                "default": 500
            }
        ],
        "existing_params": {
            "topic": "디지털 마케팅 전략"
        }
    }
    
    # 테스트 2: 웹 검색 태스크 (검색어 없음)
    search_test = {
        "task_description": "인공지능의 최신 트렌드를 조사해 주세요",
        "param_schemas": [
            {
                "name": "query",
                "description": "검색할 쿼리 또는 키워드",
                "type": "string",
                "required": True
            },
            {
                "name": "num_results",
                "description": "반환할 검색 결과 수",
                "type": "number",
                "required": False,
                "default": 5
            },
            {
                "name": "language",
                "description": "검색 결과 언어",
                "type": "string",
                "required": False,
                "default": "ko",
                "enum": ["ko", "en", "jp", "cn"]
            }
        ],
        "existing_params": {}
    }
    
    async with httpx.AsyncClient() as client:
        # 테스트 1 실행
        print("\n=== 문서 작성 태스크 테스트 ===")
        response1 = await client.post(f"{broker_url}/test/infer-params", json=writer_test)
        if response1.status_code == 200:
            result1 = response1.json()
            print("추론 결과:")
            pprint(result1["inferred_params"])
        else:
            print(f"오류: {response1.status_code} - {response1.text}")
        
        # 테스트 2 실행
        print("\n=== 웹 검색 태스크 테스트 ===")
        response2 = await client.post(f"{broker_url}/test/infer-params", json=search_test)
        if response2.status_code == 200:
            result2 = response2.json()
            print("추론 결과:")
            pprint(result2["inferred_params"])
        else:
            print(f"오류: {response2.status_code} - {response2.text}")

if __name__ == "__main__":
    asyncio.run(test_param_inference()) 