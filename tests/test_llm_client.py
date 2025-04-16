import unittest
from unittest.mock import patch, MagicMock
import pytest
import sys
import os

# 프로젝트 루트 경로를 sys.path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# litellm 모킹
mock_module = MagicMock()
mock_module.completion = MagicMock()
mock_module.acompletion = MagicMock()  # 일반 MagicMock으로 변경
sys.modules['litellm'] = mock_module
sys.modules['litellm.utils'] = MagicMock()

from common.llm_client import LLMClient

# 가짜 응답 생성 함수
def create_mock_response(content="이것은 테스트 응답입니다"):
    return {
        "id": "chatcmpl-123456789",
        "object": "chat.completion",
        "created": 1677858242,
        "model": "gpt-3.5-turbo-0613",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "index": 0,
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }

class TestLLMClient(unittest.TestCase):
    """LLMClient 클래스에 대한 테스트"""

    def setUp(self):
        """각 테스트 전 설정"""
        self.client = LLMClient(default_model="gpt-3.5-turbo")
        self.test_messages = [
            {"role": "system", "content": "당신은 유용한 AI 비서입니다."},
            {"role": "user", "content": "안녕하세요"}
        ]

    @patch('common.llm_client.completion')
    def test_complete(self, mock_completion):
        """동기 완성 메서드 테스트"""
        # 모의 응답 설정
        mock_completion.return_value = create_mock_response()
        
        # 메서드 호출
        response = self.client.complete(messages=self.test_messages)
        
        # 예상대로 호출되었는지 확인
        mock_completion.assert_called_once()
        self.assertEqual(response["choices"][0]["message"]["content"], "이것은 테스트 응답입니다")

    @patch('common.llm_client.completion')
    def test_ask(self, mock_completion):
        """ask 메서드 테스트"""
        mock_completion.return_value = create_mock_response("질문에 대한 답변입니다")
        
        result = self.client.ask("테스트 질문입니다", system_prompt="당신은 테스트용 AI입니다")
        
        self.assertEqual(result, "질문에 대한 답변입니다")
        self.assertEqual(mock_completion.call_count, 1)
        
        # 시스템 프롬프트가 포함되었는지 확인
        call_args = mock_completion.call_args[1]
        self.assertEqual(len(call_args["messages"]), 2)
        self.assertEqual(call_args["messages"][0]["role"], "system")

    @patch('common.llm_client.completion')
    def test_model_override(self, mock_completion):
        """모델 오버라이드 테스트"""
        mock_completion.return_value = create_mock_response()
        
        self.client.complete(messages=self.test_messages, model="gpt-4")
        
        # gpt-4로 호출되었는지 확인
        self.assertEqual(mock_completion.call_args[1]["model"], "gpt-4")

    @patch('common.llm_client.completion')
    def test_retry_logic(self, mock_completion):
        """재시도 로직 테스트"""
        # 첫 번째와 두 번째 호출에서 예외 발생, 세 번째 호출에서 성공
        mock_completion.side_effect = [
            Exception("API 오류"),
            Exception("네트워크 오류"),
            create_mock_response("재시도 후 성공")
        ]
        
        # max_retries를 2로 설정하여 성공할 수 있게 함
        client = LLMClient(max_retries=3, retry_delay=0.01)
        response = client.complete(messages=self.test_messages)
        
        # 3번 호출되었는지 확인
        self.assertEqual(mock_completion.call_count, 3)
        self.assertEqual(response["choices"][0]["message"]["content"], "재시도 후 성공")

    @patch('common.llm_client.completion')
    def test_max_retries_exceeded(self, mock_completion):
        """최대 재시도 초과 테스트"""
        # 모든 호출에서 예외 발생
        mock_completion.side_effect = Exception("지속적인 API 오류")
        
        # max_retries를 2로 설정
        client = LLMClient(max_retries=2, retry_delay=0.01)
        
        # 예외가 발생해야 함
        with self.assertRaises(Exception):
            client.complete(messages=self.test_messages)
        
        # 정확히 2번 재시도했는지 확인
        self.assertEqual(mock_completion.call_count, 2)

    def test_validate_messages(self):
        """메시지 검증 테스트"""
        # 유효한 메시지
        valid_messages = [
            {"role": "system", "content": "시스템 메시지"},
            {"role": "user", "content": "사용자 메시지"},
            {"role": "assistant", "content": "어시스턴트 메시지"}
        ]
        
        result = self.client._validate_messages(valid_messages)
        self.assertEqual(len(result), 3)
        
        # 역할이 없는 메시지
        invalid_messages = [{"content": "역할이 없음"}]
        with self.assertRaises(ValueError):
            self.client._validate_messages(invalid_messages)
        
        # 잘못된 역할
        invalid_role_messages = [{"role": "invalid", "content": "잘못된 역할"}]
        with self.assertRaises(ValueError):
            self.client._validate_messages(invalid_role_messages)


if __name__ == "__main__":
    unittest.main() 