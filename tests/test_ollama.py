#!/usr/bin/env python
import os
import sys
from pathlib import Path

# 프로젝트 루트 경로를 sys.path에 추가
ROOT_DIR = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(ROOT_DIR))

from common.llm_client import LLMClient

def test_ollama_models():
    """Ollama 로컬 모델 테스트"""
    client = LLMClient()
    
    models_to_test = [
        "ollama/llama3.1:8b",
        # "ollama/mistral",   # 설치했다면 주석 해제
        # "ollama/gemma:2b",  # 설치했다면 주석 해제
    ]
    
    test_prompts = [
        "hi?",
        # "파이썬으로 'Hello, World!'를 출력하는 코드를 작성해주세요.",
        # "리눅스 서버에서 메모리 사용량을 확인하는 명령어는 무엇인가요?",
    ]
    
    results = {}
    
    for model in models_to_test:
        print(f"\n{'-'*40}")
        print(f"테스트 모델: {model}")
        print(f"{'-'*40}")
        
        model_results = []
        
        for prompt in test_prompts:
            print(f"프롬프트: {prompt[:30]}...")
            
            try:
                start_time = __import__('time').time()
                response = client.ask(prompt, model=model)
                end_time = __import__('time').time()
                
                excerpt = response[:100] + "..." if len(response) > 100 else response
                print(f"응답: {excerpt}")
                print(f"응답 시간: {end_time - start_time:.2f}초\n")
                
                model_results.append({
                    "prompt": prompt,
                    "response": response,
                    "time": end_time - start_time
                })
                
            except Exception as e:
                print(f"오류 발생: {str(e)}\n")
                model_results.append({
                    "prompt": prompt,
                    "error": str(e)
                })
        
        results[model] = model_results
    
    return results


if __name__ == "__main__":
    print("Ollama 로컬 모델 테스트 실행 중...")
    results = test_ollama_models()
    
    print("\n테스트 요약:")
    for model, tests in results.items():
        success_count = sum(1 for t in tests if "error" not in t)
        print(f"{model}: {success_count}/{len(tests)} 테스트 성공") 