#!/usr/bin/env python
import os
import sys
from pathlib import Path
import json
from datetime import datetime

# 프로젝트 루트 경로를 sys.path에 추가
ROOT_DIR = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(ROOT_DIR))

from common.llm_client import LLMClient

def compare_models():
    """여러 모델의 응답을 비교 테스트"""
    client = LLMClient()
    
    # 테스트할 모델 목록 (사용 가능한 API 키와 설치된 모델에 따라 조정)
    models_to_test = [
        # "gpt-3.5-turbo",     # OpenAI API 키 필요
        "gpt-4o-mini",     # OpenAI API 키 필요
        "claude-3-haiku-20240307",  # Anthropic API 키 필요
        "ollama/tinyllama",     # Ollama 설치 필요
        # "ollama/gemma:2b"
    ]
    
    # 테스트할 프롬프트 목록
    test_prompts = [
        "hi",
        # "인공지능의 미래에 대해 간략히 설명해주세요.",
        # "다음 Python 코드의 문제점을 찾아주세요: def divide(a, b): return a/b",
        # "\"지속 가능한 개발\"이 왜 중요한지 3가지 이유를 알려주세요.",
    ]
    
    results = {}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for prompt in test_prompts:
        prompt_results = {}
        print(f"\n{'-'*60}")
        print(f"테스트 프롬프트: {prompt}")
        print(f"{'-'*60}")
        
        for model in models_to_test:
            try:
                print(f"\n모델: {model}")
                
                start_time = __import__('time').time()
                response = client.ask(prompt, model=model)
                end_time = __import__('time').time()
                
                prompt_results[model] = {
                    "response": response,
                    "time": round(end_time - start_time, 2)
                }
                
                print(f"응답 시간: {prompt_results[model]['time']}초")
                print(f"응답 내용 (일부):\n{response[:200]}...\n")
                
            except Exception as e:
                print(f"오류 발생: {str(e)}")
                prompt_results[model] = {"error": str(e)}
        
        results[prompt] = prompt_results
    
    # 결과를 JSON 파일로 저장
    output_path = ROOT_DIR / "tests" / "results" / f"model_comparison_{timestamp}.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n결과가 저장되었습니다: {output_path}")
    return results


if __name__ == "__main__":
    print("모델 비교 테스트 실행 중...")
    compare_models() 