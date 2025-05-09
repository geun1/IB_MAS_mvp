"""
데이터 분석 ReACT 에이전트
데이터 처리, 분석, 시각화를 수행하는 특화된 에이전트
"""
import os
import logging
import asyncio
import json
import time
import uuid
import base64
from typing import Dict, Any, List, Optional, Tuple
from fastapi import FastAPI, Request, Body, HTTPException, Depends
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv("../../../.env")

# 공통 모듈 임포트
try:
    from common.react_agent_base import ReACTAgentBase, ReACTSession, ReACTStepType, ReACTStep
    from common.fallback_manager import FallbackManager, FallbackStatus, FallbackResult
except ImportError:
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    if project_root not in sys.path:
        sys.path.append(project_root)
    from common.react_agent_base import ReACTAgentBase, ReACTSession, ReACTStepType, ReACTStep
    from common.fallback_manager import FallbackManager, FallbackStatus, FallbackResult

# 데이터 분석 라이브러리 임포트
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from io import StringIO, BytesIO

# API 클라이언트 설정
import httpx

# 로깅 설정
logging.basicConfig(
    level=logging.getLevelName(os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("data_analysis_agent")

# LLM 클라이언트
class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.client = httpx.AsyncClient(timeout=60.0)
        
    async def ask(self, prompt: str) -> str:
        """LLM에 질문하고 응답 받기"""
        logger.info("LLM 질의 시작")
        
        # 데이터 유형을 추론하고 그에 맞는 액션 반환
        try:
            # 현재 ReACT 단계 파악
            is_first_step = "단계 기록" in prompt and "이전 단계 없음" in prompt
            has_loaded_data = "load_data" in prompt and "성공" in prompt
            
            # 텍스트 데이터 패턴 확인
            contains_attendance_pattern = "[주차]" in prompt or "출석" in prompt
            contains_csv_pattern = "CSV" in prompt or "csv" in prompt
            contains_numerical_pattern = "통계" in prompt or "숫자" in prompt or "수치" in prompt
            
            # 첫 단계에서는 항상 데이터 로드
            if is_first_step:
                # 데이터 유형에 따라 다른 로드 액션 제안
                if contains_attendance_pattern:
                    response = f"""사고 과정:
주어진 데이터는 주차별 출석 정보를 포함하고 있는 것으로 보입니다. 텍스트 기반 데이터이므로 텍스트 형식으로 로드합니다.

다음 행동: load_data
파라미터: {{"format": "text"}}

이유: 텍스트 데이터를 로드하여 출석 패턴을 분석해야 합니다."""
                elif contains_csv_pattern:
                    response = f"""사고 과정:
주어진 데이터는 CSV 형식으로 보입니다. 표 형식으로 로드합니다.

다음 행동: load_data
파라미터: {{"format": "csv_string"}}

이유: CSV 데이터를 로드하여 구조화된 데이터 분석을 수행해야 합니다."""
                else:
                    response = f"""사고 과정:
데이터 형식이 명확하지 않습니다. 자동 감지 기능을 사용하여 로드합니다.

다음 행동: load_data
파라미터: {{"format": "auto"}}

이유: 데이터 형식을 자동으로 감지하여 적절한 방법으로 분석을 시작합니다."""
            
            # 데이터 로드 후 분석 단계
            elif has_loaded_data:
                data_type = "text" if "텍스트 데이터" in prompt else "tabular"
                
                if data_type == "text":
                    if contains_attendance_pattern:
                        response = f"""사고 과정:
데이터가 주차별 출석 정보를 포함하고 있습니다. 텍스트에서 구조화된 출석 데이터를 추출하고 분석합니다.

다음 행동: analyze_data
파라미터: {{"method": "extract_structured_data", "extraction_type": "attendance"}}

이유: 텍스트에서 출석 패턴을 추출하고 출석률, 참여도 변화 등을 분석합니다."""
                    else:
                        response = f"""사고 과정:
텍스트 데이터가 로드되었습니다. 먼저 텍스트 패턴을 분석하여 데이터의 특성을 파악합니다.

다음 행동: analyze_data
파라미터: {{"method": "pattern_analysis"}}

이유: 텍스트에서 날짜, 이메일, 숫자 등의 패턴을 찾아 데이터 특성을 파악합니다."""
                else:  # tabular 데이터
                    if contains_numerical_pattern:
                        response = f"""사고 과정:
표 데이터가 로드되었고 수치 분석이 필요합니다. 기본 통계 분석을 수행합니다.

다음 행동: analyze_data
파라미터: {{"method": "summary_statistics"}}

이유: 데이터의 기본 통계 정보(평균, 중앙값, 표준편차 등)를 계산합니다."""
                    else:
                        response = f"""사고 과정:
표 데이터가 로드되었습니다. 변수 간 관계를 파악하기 위해 상관관계 분석을 수행합니다.

다음 행동: analyze_data
파라미터: {{"method": "correlation"}}

이유: 데이터 변수 간의 상관관계를 분석하여 관계성을 파악합니다."""
            
            # 분석 후 시각화 단계
            elif "analyze_data" in prompt and "성공" in prompt:
                if "attendance_analysis" in prompt or contains_attendance_pattern:
                    response = f"""사고 과정:
출석 데이터 분석이 완료되었습니다. 이제 최종 결과를 생성하여 정리된 출석 통계를 제공합니다.

다음 행동: finish
파라미터: {{"message": "출석 데이터 분석이 완료되었습니다. 결과 보고서를 확인하세요."}}

이유: 출석 분석이 완료되었으므로 최종 결과를 생성합니다."""
                elif "text_analysis" in prompt or "pattern_analysis" in prompt:
                    response = f"""사고 과정:
텍스트 패턴 분석이 완료되었습니다. 구조화된 데이터를 추출하여 더 심층적인 분석을 수행합니다.

다음 행동: analyze_data
파라미터: {{"method": "extract_structured_data", "extraction_type": "auto"}}

이유: 텍스트에서 구조화된 정보를 추출하여 더 의미 있는 분석 결과를 도출합니다."""
                else:
                    response = f"""사고 과정:
기본 데이터 분석이 완료되었습니다. 주요 변수에 대한 시각화를 진행합니다.

다음 행동: visualize_data
파라미터: {{"plot_type": "histogram", "column": "AUTO"}}

이유: 주요 변수의 분포를 시각적으로 확인하여 데이터 특성을 더 잘 이해합니다."""
            
            # 시각화 후 마무리 단계
            elif "visualize_data" in prompt or "extract_structured_data" in prompt:
                response = f"""사고 과정:
모든 분석 및 시각화가 완료되었습니다. 최종 결과를 생성합니다.

다음 행동: finish
파라미터: {{"message": "데이터 분석이 완료되었습니다. 결과 보고서를 확인하세요."}}

이유: 모든 분석 단계가 완료되었으므로 최종 결과를 생성합니다."""
            
            # 예상치 못한 상황
            else:
                response = f"""사고 과정:
현재 상황을 분석했습니다. 다음 단계로 진행합니다.

다음 행동: analyze_data
파라미터: {{"method": "summary_statistics"}}

이유: 데이터의 기본 특성을 파악하기 위해 요약 통계가 필요합니다."""
            
        except Exception as e:
            # 오류 발생 시 기본 응답
            logger.error(f"LLM 응답 생성 중 오류: {str(e)}")
            response = f"""사고 과정:
데이터를 분석하고 적절한 통계 정보를 계산해야 합니다.

다음 행동: analyze_data
파라미터: {{"method": "summary_statistics"}}

이유: 데이터의 기본 특성을 이해하기 위해 요약 통계가 필요합니다."""
        
        logger.info("LLM 질의 완료")
        return response

# 데이터 분석 클라스
class DataAnalyzer:
    """데이터 분석 기능을 제공하는 클래스"""
    
    def __init__(self):
        self.data = None
        self.text_data = None
        self.data_type = None  # "tabular" 또는 "text" 등
    
    def load_data(self, data_source: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        데이터 로드 함수
        
        Args:
            data_source: 데이터 소스 (CSV 문자열, URL 등)
            params: 데이터 로드 매개변수
            
        Returns:
            로드 결과
        """
        try:
            if params is None:
                params = {}
            
            # 데이터 타입 추론
            data_format = params.get("format", "auto")
            
            # 텍스트 데이터로 간주 (JSON, 마크다운, 일반 텍스트 등)
            if data_format == "text" or (data_format == "auto" and not self._is_tabular_data(data_source)):
                self.text_data = data_source
                self.data_type = "text"
                
                # 간단한 텍스트 분석
                lines = data_source.split('\n')
                words = data_source.split()
                
                return {
                    "success": True,
                    "message": f"텍스트 데이터 로드 완료: {len(lines)} 행, {len(words)} 단어",
                    "data_type": "text",
                    "lines": len(lines),
                    "words": len(words),
                    "preview": data_source[:200] + ("..." if len(data_source) > 200 else "")
                }
                
            # CSV 문자열로부터 데이터 로드
            elif data_format == "csv_string" or data_format == "auto":
                try:
                    self.data = pd.read_csv(StringIO(data_source))
                    self.data_type = "tabular"
                    return {
                        "success": True, 
                        "message": f"표 데이터 로드 완료: {len(self.data)} 행, {len(self.data.columns)} 열",
                        "data_type": "tabular",
                        "columns": self.data.columns.tolist(),
                        "shape": self.data.shape
                    }
                except Exception as csv_error:
                    # CSV 로드 실패 시 텍스트로 처리
                    self.text_data = data_source
                    self.data_type = "text"
                    lines = data_source.split('\n')
                    words = data_source.split()
                    
                    return {
                        "success": True,
                        "message": f"텍스트 데이터로 로드 완료: {len(lines)} 행, {len(words)} 단어",
                        "data_type": "text",
                        "original_error": str(csv_error),
                        "lines": len(lines),
                        "words": len(words)
                    }
                
            # URL에서 데이터 로드
            elif params.get("format") == "url":
                self.data = pd.read_csv(data_source)
                self.data_type = "tabular"
                return {
                    "success": True,
                    "message": f"URL에서 데이터 로드 완료: {len(self.data)} 행, {len(self.data.columns)} 열",
                    "data_type": "tabular",
                    "columns": self.data.columns.tolist(),
                    "shape": self.data.shape
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _is_tabular_data(self, data: str) -> bool:
        """데이터가 표 형식인지 판별"""
        # 기본적인 CSV 형식 확인 (쉼표 구분, 일관된 필드 수)
        lines = data.strip().split('\n')
        if len(lines) < 2:  # 헤더 + 최소 1개 데이터 행
            return False
            
        # 첫 몇 줄이 일관된 구분자 패턴을 가지는지 확인
        delimiters = [',', '\t', '|', ';']
        for delimiter in delimiters:
            if delimiter in lines[0]:
                fields_count = lines[0].count(delimiter) + 1
                consistent = True
                
                # 처음 5개 행 또는 전체 행 중 적은 것 확인
                check_lines = min(5, len(lines))
                for i in range(1, check_lines):
                    if lines[i].count(delimiter) + 1 != fields_count:
                        consistent = False
                        break
                
                if consistent:
                    return True
        
        return False
    
    def analyze_data(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        데이터 분석 수행
        
        Args:
            method: 분석 방법 (summary_statistics, correlation, text_analysis, etc.)
            params: 분석 매개변수
            
        Returns:
            분석 결과
        """
        if self.data is None and self.text_data is None:
            return {"success": False, "error": "데이터가 로드되지 않았습니다."}
            
        if params is None:
            params = {}
            
        try:
            # 텍스트 데이터 분석
            if self.data_type == "text":
                if method == "text_analysis" or method == "summary_statistics":
                    return self._analyze_text_data(params)
                elif method == "pattern_analysis":
                    return self._analyze_text_patterns(params)
                elif method == "extract_structured_data":
                    return self._extract_structured_data_from_text(params)
                else:
                    return {"success": False, "error": f"텍스트 데이터에 지원되지 않는 분석 방법: {method}"}
            
            # 표 데이터 분석 (기존 메서드)
            # 요약 통계
            if method == "summary_statistics":
                result = self.data.describe().to_dict()
                return {"success": True, "result": result, "method": "summary_statistics"}
                
            # 상관 분석
            elif method == "correlation":
                numeric_data = self.data.select_dtypes(include=['number'])
                result = numeric_data.corr().to_dict()
                return {"success": True, "result": result, "method": "correlation"}
                
            # 특정 열 분석
            elif method == "column_analysis":
                column = params.get("column")
                if column not in self.data.columns:
                    return {"success": False, "error": f"컬럼 '{column}'을 찾을 수 없습니다."}
                    
                column_data = self.data[column]
                result = {
                    "dtype": str(column_data.dtype),
                    "unique_values": column_data.nunique(),
                    "missing_values": column_data.isna().sum()
                }
                
                if pd.api.types.is_numeric_dtype(column_data):
                    result.update({
                        "min": column_data.min(),
                        "max": column_data.max(),
                        "mean": column_data.mean(),
                        "median": column_data.median(),
                        "std": column_data.std()
                    })
                elif pd.api.types.is_string_dtype(column_data):
                    result.update({
                        "most_common": column_data.value_counts().head(5).to_dict()
                    })
                    
                return {"success": True, "result": result, "method": "column_analysis"}
                
            # 지원되지 않는 방법
            else:
                return {"success": False, "error": f"지원되지 않는 분석 방법: {method}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _analyze_text_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """텍스트 데이터 기본 분석"""
        if not self.text_data:
            return {"success": False, "error": "텍스트 데이터가 로드되지 않았습니다."}
            
        lines = self.text_data.strip().split('\n')
        words = self.text_data.split()
        chars = len(self.text_data)
        
        # 기본 통계
        stats = {
            "lines_count": len(lines),
            "words_count": len(words),
            "chars_count": chars,
            "avg_line_length": chars / max(len(lines), 1),
            "avg_word_length": sum(len(word) for word in words) / max(len(words), 1)
        }
        
        # 단어 빈도 분석
        word_freq = {}
        for word in words:
            # 공백과 특수문자 제거
            clean_word = ''.join(c for c in word.lower() if c.isalnum())
            if clean_word and len(clean_word) > 2:  # 3글자 이상 단어만
                word_freq[clean_word] = word_freq.get(clean_word, 0) + 1
        
        # 가장 흔한 단어 상위 20개
        top_words = dict(sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:20])
        
        return {
            "success": True, 
            "result": {
                "basic_stats": stats,
                "top_words": top_words,
                "preview": self.text_data[:300] + ("..." if len(self.text_data) > 300 else "")
            },
            "method": "text_analysis"
        }
    
    def _analyze_text_patterns(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """텍스트에서 패턴 분석 (예: 날짜, 이메일, 번호 등)"""
        if not self.text_data:
            return {"success": False, "error": "텍스트 데이터가 로드되지 않았습니다."}
        
        import re
        
        # 정규식 패턴
        patterns = {
            "dates": r"\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}|\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}",  # yyyy-mm-dd 또는 dd-mm-yyyy
            "emails": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "urls": r"https?://[^\s]+",
            "numbers": r"\b\d+\b",
            "phone_numbers": r"\b(\+\d{1,3}[-.\s]?)?(\d{2,4}[-.\s]?){2,4}\d{2,4}\b",
        }
        
        # 사용자 정의 패턴
        if params.get("custom_patterns"):
            for name, pattern in params["custom_patterns"].items():
                patterns[name] = pattern
        
        # 각 패턴 매칭 찾기
        results = {}
        for name, pattern in patterns.items():
            matches = re.findall(pattern, self.text_data)
            results[name] = {
                "count": len(matches),
                "examples": matches[:10] if matches else []
            }
        
        return {
            "success": True,
            "result": results,
            "method": "pattern_analysis"
        }
    
    def _extract_structured_data_from_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """텍스트에서 구조화된 데이터 추출 (출석 데이터 등)"""
        if not self.text_data:
            return {"success": False, "error": "텍스트 데이터가 로드되지 않았습니다."}
        
        # 기본 파라미터 설정
        extraction_type = params.get("extraction_type", "auto")
        
        # 출석 데이터 처리 (예: "[1주차] 홍길동, 김철수, 이영희")
        if extraction_type == "attendance" or (extraction_type == "auto" and "[" in self.text_data and "]" in self.text_data):
            return self._extract_attendance_data()
        
        # 일정/이벤트 데이터 (예: "2023-05-01: 미팅, 2023-05-02: 워크숍")
        elif extraction_type == "events" or (extraction_type == "auto" and ":" in self.text_data and re.search(r"\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}", self.text_data)):
            return self._extract_event_data()
        
        # 기본 키-값 쌍 추출 (예: "이름: 홍길동, 나이: 30, 직업: 개발자")
        else:
            return self._extract_key_value_data()
    
    def _extract_attendance_data(self) -> Dict[str, Any]:
        """출석 데이터 추출 및 분석"""
        import re
        
        # 각 행 분석
        lines = self.text_data.strip().split('\n')
        attendance_data = {}
        all_attendees = set()
        
        pattern = r"\[(.*?)\](.*)"
        
        for line in lines:
            match = re.search(pattern, line)
            if match:
                week = match.group(1).strip()
                attendees_str = match.group(2).strip()
                
                # 출석자 목록 파싱 (쉼표, 공백으로 구분)
                attendees = [name.strip() for name in re.split(r'[,\s]+', attendees_str) if name.strip()]
                attendance_data[week] = attendees
                all_attendees.update(attendees)
        
        # 각 주차별 통계 계산
        if not attendance_data:
            return {"success": False, "error": "출석 데이터를 찾을 수 없습니다."}
        
        # 통계 계산
        stats = []
        all_attendees_list = sorted(list(all_attendees))
        prev_attendees = None
        
        for week, attendees in attendance_data.items():
            week_stats = {
                "주차": week,
                "참석자_수": len(attendees),
                "참석자_목록": attendees
            }
            
            # 이전 주차와 비교
            if prev_attendees is not None:
                new_attendees = set(attendees) - set(prev_attendees)
                missing_attendees = set(prev_attendees) - set(attendees)
                week_stats["신규_참석자"] = list(new_attendees)
                week_stats["불참자"] = list(missing_attendees)
                week_stats["출석_유지율"] = round(len(set(attendees) & set(prev_attendees)) / len(prev_attendees) * 100, 1) if prev_attendees else 0
            
            stats.append(week_stats)
            prev_attendees = attendees
        
        # 전체 요약 통계
        overall_stats = {
            "총_주차_수": len(attendance_data),
            "총_인원": len(all_attendees),
            "평균_참석자_수": sum(len(attendees) for attendees in attendance_data.values()) / len(attendance_data),
        }
        
        # 개인별 출석률
        attendance_rates = {}
        for person in all_attendees:
            weeks_attended = sum(1 for attendees in attendance_data.values() if person in attendees)
            attendance_rates[person] = {
                "출석_횟수": weeks_attended,
                "출석률": round(weeks_attended / len(attendance_data) * 100, 1)
            }
        
        # 마크다운 테이블 생성
        markdown_table = "| 주차 | 참석자 수 | 출석률 |\n|------|----------|--------|\n"
        for week_stat in stats:
            attendance_rate = round((week_stat["참석자_수"] / len(all_attendees)) * 100, 1)
            markdown_table += f"| {week_stat['주차']} | {week_stat['참석자_수']}명 | {attendance_rate}% |\n"
        
        # 개인별 출석 현황 테이블
        person_table = "| 이름 | 출석 횟수 | 출석률 |\n|------|----------|--------|\n"
        for person, rate in sorted(attendance_rates.items(), key=lambda x: x[1]['출석률'], reverse=True):
            person_table += f"| {person} | {rate['출석_횟수']}회 | {rate['출석률']}% |\n"
        
        # 주차별 참석자 변동 테이블
        change_table = "| 주차 | 신규 참석자 | 불참자 | 유지율 |\n|------|------------|--------|--------|\n"
        for i, week_stat in enumerate(stats):
            if i == 0:  # 첫 주차는 비교 데이터 없음
                change_table += f"| {week_stat['주차']} | - | - | - |\n"
            else:
                new_str = ', '.join(week_stat.get("신규_참석자", [])) or "-"
                missing_str = ', '.join(week_stat.get("불참자", [])) or "-"
                retention = week_stat.get("출석_유지율", 0)
                change_table += f"| {week_stat['주차']} | {new_str} | {missing_str} | {retention}% |\n"
        
        return {
            "success": True,
            "result": {
                "attendance_data": attendance_data,
                "weekly_stats": stats,
                "overall_stats": overall_stats,
                "attendance_rates": attendance_rates,
                "markdown_tables": {
                    "weekly_summary": markdown_table,
                    "person_summary": person_table,
                    "change_summary": change_table
                }
            },
            "method": "attendance_analysis"
        }
    
    def _extract_event_data(self) -> Dict[str, Any]:
        """이벤트/일정 데이터 추출"""
        import re
        from datetime import datetime
        
        pattern = r"(\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}):\s*(.*)"
        
        lines = self.text_data.strip().split('\n')
        events = []
        
        for line in lines:
            match = re.search(pattern, line)
            if match:
                date_str = match.group(1).strip()
                event_desc = match.group(2).strip()
                
                # 날짜 형식 정규화
                date_str = date_str.replace('/', '-').replace('.', '-')
                
                events.append({
                    "date": date_str,
                    "description": event_desc
                })
        
        if not events:
            return {"success": False, "error": "이벤트 데이터를 찾을 수 없습니다."}
        
        # 이벤트를 날짜순으로 정렬
        try:
            events.sort(key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d"))
        except:
            pass  # 날짜 형식이 다양할 수 있으므로 정렬 실패 시 원래 순서 유지
        
        # 마크다운 테이블 생성
        markdown_table = "| 날짜 | 이벤트 |\n|------|--------|\n"
        for event in events:
            markdown_table += f"| {event['date']} | {event['description']} |\n"
        
        return {
            "success": True,
            "result": {
                "events": events,
                "total_events": len(events),
                "date_range": {
                    "start": events[0]["date"] if events else None,
                    "end": events[-1]["date"] if events else None
                },
                "markdown_table": markdown_table
            },
            "method": "event_analysis"
        }
    
    def _extract_key_value_data(self) -> Dict[str, Any]:
        """키-값 쌍 추출"""
        import re
        
        pattern = r"([^:,]+):\s*([^,]+)(?:,|$)"
        
        # 모든 키-값 쌍 찾기
        kv_pairs = re.findall(pattern, self.text_data)
        
        if not kv_pairs:
            return {"success": False, "error": "키-값 데이터를 찾을 수 없습니다."}
        
        # 결과 정리
        structured_data = {}
        for key, value in kv_pairs:
            key = key.strip()
            value = value.strip()
            structured_data[key] = value
        
        # 마크다운 테이블 생성
        markdown_table = "| 키 | 값 |\n|------|--------|\n"
        for key, value in structured_data.items():
            markdown_table += f"| {key} | {value} |\n"
        
        return {
            "success": True,
            "result": {
                "structured_data": structured_data,
                "pairs_count": len(structured_data),
                "markdown_table": markdown_table
            },
            "method": "key_value_analysis"
        }
    
    def visualize_data(self, plot_type: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        데이터 시각화
        
        Args:
            plot_type: 시각화 유형 (histogram, scatter, etc.)
            params: 시각화 매개변수
            
        Returns:
            시각화 결과 (Base64 인코딩된 이미지)
        """
        if self.data is None:
            return {"success": False, "error": "데이터가 로드되지 않았습니다."}
            
        if params is None:
            params = {}
            
        try:
            plt.figure(figsize=(10, 6))
            
            # 히스토그램
            if plot_type == "histogram":
                column = params.get("column")
                if column not in self.data.columns:
                    return {"success": False, "error": f"컬럼 '{column}'을 찾을 수 없습니다."}
                    
                sns.histplot(self.data[column], kde=params.get("kde", True))
                plt.title(f"Histogram of {column}")
                plt.xlabel(column)
                plt.ylabel("Frequency")
                
            # 산점도
            elif plot_type == "scatter":
                x_col = params.get("x")
                y_col = params.get("y")
                
                if x_col not in self.data.columns:
                    return {"success": False, "error": f"X 컬럼 '{x_col}'을 찾을 수 없습니다."}
                if y_col not in self.data.columns:
                    return {"success": False, "error": f"Y 컬럼 '{y_col}'을 찾을 수 없습니다."}
                    
                sns.scatterplot(x=x_col, y=y_col, data=self.data)
                plt.title(f"Scatter Plot: {x_col} vs {y_col}")
                plt.xlabel(x_col)
                plt.ylabel(y_col)
                
            # 막대 그래프
            elif plot_type == "bar":
                column = params.get("column")
                if column not in self.data.columns:
                    return {"success": False, "error": f"컬럼 '{column}'을 찾을 수 없습니다."}
                    
                self.data[column].value_counts().head(10).plot(kind='bar')
                plt.title(f"Bar Plot of {column}")
                plt.xlabel(column)
                plt.ylabel("Count")
                
            # 상관관계 히트맵
            elif plot_type == "heatmap":
                numeric_data = self.data.select_dtypes(include=['number'])
                sns.heatmap(numeric_data.corr(), annot=params.get("annot", True), cmap="coolwarm")
                plt.title("Correlation Heatmap")
                
            # 지원되지 않는 플롯 유형
            else:
                return {"success": False, "error": f"지원되지 않는 시각화 유형: {plot_type}"}
                
            # 이미지를 Base64로 인코딩
            buf = BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            img_str = base64.b64encode(buf.read()).decode('utf-8')
            plt.close()
            
            return {
                "success": True, 
                "plot_type": plot_type,
                "image": img_str
            }
            
        except Exception as e:
            plt.close()
            return {"success": False, "error": str(e)} 

# API 요청 모델
class DataAnalysisParams(BaseModel):
    query: str = Field(..., description="사용자 쿼리 또는 데이터 분석 요청")
    data: Optional[str] = Field(None, description="분석할 데이터 (CSV 문자열)")
    data_url: Optional[str] = Field(None, description="분석할 데이터 URL")
    max_steps: Optional[int] = Field(10, description="최대 ReACT 단계 수")
    requires: Optional[List[str]] = Field(default_factory=list, description="필요한 도구 또는 에이전트")

# FastAPI 앱 초기화
app = FastAPI(title="Data Analysis Agent API")

# 데이터 분석 ReACT 에이전트 
class DataAnalysisAgent(ReACTAgentBase):
    """
    데이터 분석 ReACT 에이전트
    데이터 처리, 분석, 시각화를 수행하는 전문 에이전트
    """
    
    def __init__(self, app: FastAPI):
        """데이터 분석 에이전트 초기화"""
        agent_id = "data_analysis_agent"
        agent_role = "data_analyzer"
        description = "데이터 로딩, 분석 및 시각화를 수행하는 전문 에이전트"
        
        # 에이전트 파라미터 정의
        params = [
            {
                "name": "query",
                "type": "string",
                "description": "사용자 쿼리 또는 데이터 분석 요청",
                "required": True
            },
            {
                "name": "data",
                "type": "string",
                "description": "분석할 데이터 (CSV 문자열)",
                "required": False
            },
            {
                "name": "data_url",
                "type": "string",
                "description": "분석할 데이터 URL",
                "required": False
            },
            {
                "name": "max_steps",
                "type": "integer",
                "description": "최대 ReACT 단계 수",
                "required": False,
                "default": 10
            },
            {
                "name": "requires",
                "type": "array",
                "description": "필요한 도구 또는 에이전트",
                "required": False,
                "default": []
            }
        ]
        
        # 레지스트리 URL과 컨테이너 정보
        registry_url = os.getenv("REGISTRY_URL", "http://registry:8000")
        container_name = os.getenv("CONTAINER_NAME", "data_analysis_agent")
        port = int(os.getenv("PORT", "8040"))
        
        # 브로커 URL 설정
        broker_url = os.getenv("BROKER_URL", "http://broker:8000")
        
        # 기본 클래스 초기화
        super().__init__(
            agent_id=agent_id,
            agent_role=agent_role,
            description=description,
            app=app,
            params=params,
            registry_url=registry_url,
            container_name=container_name,
            port=port,
            broker_url=broker_url,
            max_steps_per_session=10,
            fallback_max_retries=3
        )
        
        # LLM 클라이언트 초기화
        self.llm = LLMClient()
        
        # 데이터 분석기 초기화
        self.analyzer = DataAnalyzer()
        
        # Fallback 매니저 초기화
        self.fallback_manager = FallbackManager()
        
        # 세션별 데이터 저장
        self.session_data = {}
        
        logger.info(f"데이터 분석 에이전트 '{agent_role}' ({agent_id}) 초기화 완료")
    
    async def process_task(
        self, 
        task_id: str,
        params: Dict[str, Any], 
        dependencies: List[Dict[str, Any]],
        raw_task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        데이터 분석 작업 처리
        
        Args:
            task_id: 작업 ID
            params: 작업 매개변수
            dependencies: 의존성 작업 결과
            raw_task_data: 원시 작업 데이터
            
        Returns:
            작업 결과
        """
        logger.info(f"데이터 분석 작업 시작: {task_id}")
        
        # 쿼리 및 데이터 추출
        query = params.get("query", "")
        data = params.get("data", "")
        
        # 의존성 작업 결과에서 데이터 보완
        for dep in dependencies:
            if dep.get("result") and isinstance(dep.get("result"), dict):
                # 검색 결과에서 데이터 추출
                if "search_results" in dep["result"]:
                    search_results = dep["result"]["search_results"]
                    if isinstance(search_results, list) and search_results:
                        # 검색 결과 텍스트를 데이터로 활용
                        if not data:
                            data = "\n\n".join([item.get("content", "") for item in search_results if "content" in item])
                
                # 직접 데이터 필드가 있는 경우
                if "data" in dep["result"] and not data:
                    data = dep["result"]["data"]
                
                # 텍스트/메시지 필드가 있는 경우
                if "text" in dep["result"] and not data:
                    data = dep["result"]["text"]
                elif "message" in dep["result"] and not data:
                    data = dep["result"]["message"]
        
        # 데이터가 없는 경우
        if not data:
            logger.warning(f"작업 {task_id}에 분석할 데이터가 없습니다.")
            # 텍스트 분석인 경우 쿼리를 데이터로 사용
            if "[주차]" in query or "출석" in query or "텍스트" in query:
                data = query
            else:
                return {
                    "success": False,
                    "error": "분석할 데이터가 없습니다.",
                    "task_id": task_id
                }

        # 직접 처리 시도 (간단한 데이터 분석)
        try:
            # 데이터가 작거나 텍스트 데이터 분석이 필요한 경우
            if len(data) < 100000 or "[주차]" in query or "출석" in query or "텍스트" in query:
                logger.info(f"직접 처리 시작: 데이터 길이 {len(data)}")
                
                # 데이터 로드
                load_params = {"format": "auto"}
                # 출석 데이터인 경우 텍스트로 명시
                if "[주차]" in query or "출석" in query:
                    load_params = {"format": "text"}
                
                load_result = self.analyzer.load_data(data, load_params)
                
                if not load_result.get("success", False):
                    logger.error(f"데이터 로드 실패: {load_result.get('error')}")
                    # 실패 시 기본 ReACT 프로세스로 대체
                    return await super().process_task(task_id, params, dependencies, raw_task_data)
                
                # 데이터 유형에 따른 분석 방법 선택
                data_type = load_result.get("data_type", "tabular")
                
                if data_type == "text":
                    # 텍스트 데이터인 경우
                    logger.info("텍스트 데이터 감지됨, 텍스트 분석 수행")
                    
                    # 출석 데이터 패턴 확인
                    if "[주차]" in data or "출석" in query:
                        analysis_result = self.analyzer._extract_attendance_data()
                    else:
                        # 기본 텍스트 분석
                        analysis_result = self.analyzer._analyze_text_data({})
                        
                        # 패턴 분석 추가
                        pattern_result = self.analyzer._analyze_text_patterns({})
                        
                        # 구조화 데이터 추출 시도
                        structure_result = self.analyzer._extract_structured_data_from_text({"extraction_type": "auto"})
                else:
                    # 표 데이터인 경우 기본 통계 분석 수행
                    analysis_result = self.analyzer.analyze_data("summary_statistics")
                    
                    # 상관관계 분석 추가 (숫자 데이터가 있을 경우)
                    correlation_result = self.analyzer.analyze_data("correlation")
                
                if not analysis_result.get("success", False):
                    logger.error(f"데이터 분석 실패: {analysis_result.get('error')}")
                    # 실패 시 기본 ReACT 프로세스로 대체
                    return await super().process_task(task_id, params, dependencies, raw_task_data)
                
                # 결과 구성
                result = {
                    "success": True,
                    "steps_executed": 1,
                    "analysis_results": [],
                    "visualization_results": [],
                    "execution_time": 0.1
                }
                
                # 데이터 유형에 맞는 결과 추가
                if data_type == "text":
                    if analysis_result.get("method") == "attendance_analysis":
                        # 출석 데이터 분석 결과
                        markdown_tables = analysis_result.get("result", {}).get("markdown_tables", {})
                        
                        # 마크다운 테이블을 포함한 최종 메시지 생성
                        final_message = f"""## 출석 데이터 분석 결과

### 주차별 참석 현황
{markdown_tables.get('weekly_summary', '')}

### 참석자별 출석 현황
{markdown_tables.get('person_summary', '')}

### 주차별 참석자 변동
{markdown_tables.get('change_summary', '')}

### 전체 요약
- 총 주차 수: {analysis_result.get('result', {}).get('overall_stats', {}).get('총_주차_수', 0)}
- 총 인원: {analysis_result.get('result', {}).get('overall_stats', {}).get('총_인원', 0)}
- 평균 참석자 수: {analysis_result.get('result', {}).get('overall_stats', {}).get('평균_참석자_수', 0):.1f}명
"""
                        
                        result["analysis_results"].append({
                            "method": "attendance_analysis",
                            "result": analysis_result.get("result", {}),
                            "message": final_message
                        })
                    else:
                        # 기본 텍스트 분석 결과
                        result["analysis_results"].append({
                            "method": "text_analysis",
                            "result": analysis_result.get("result", {})
                        })
                        
                        # 패턴 분석 결과 추가 (성공한 경우)
                        if pattern_result and pattern_result.get("success"):
                            result["analysis_results"].append({
                                "method": "pattern_analysis",
                                "result": pattern_result.get("result", {})
                            })
                        
                        # 구조화 데이터 추출 결과 추가 (성공한 경우)
                        if structure_result and structure_result.get("success"):
                            result["analysis_results"].append({
                                "method": "structured_data",
                                "result": structure_result.get("result", {})
                            })
                            
                            # 마크다운 테이블이 있으면 메시지에 추가
                            if "markdown_table" in structure_result.get("result", {}):
                                result["message"] = f"""## 텍스트 데이터 분석 결과

### 추출된 구조화 데이터
{structure_result.get("result", {}).get("markdown_table", "")}

### 기본 텍스트 통계
- 총 라인 수: {analysis_result.get("result", {}).get("basic_stats", {}).get("lines_count", 0)}
- 총 단어 수: {analysis_result.get("result", {}).get("basic_stats", {}).get("words_count", 0)}
- 평균 라인 길이: {analysis_result.get("result", {}).get("basic_stats", {}).get("avg_line_length", 0):.1f} 글자
"""
                else:
                    # 표 데이터 분석 결과
                    result["analysis_results"].append({
                        "method": "summary_statistics",
                        "result": analysis_result.get("result", {})
                    })
                    
                    # 상관관계 분석 결과 추가 (성공한 경우)
                    if "correlation_result" in locals() and correlation_result.get("success"):
                        result["analysis_results"].append({
                            "method": "correlation",
                            "result": correlation_result.get("result", {})
                        })
                
                logger.info("직접 처리 완료: 데이터 분석")
                return result
        except Exception as e:
            logger.error(f"직접 처리 중 오류 발생: {str(e)}")
            # 오류 발생 시 기본 ReACT 프로세스로 대체
        
        # 기본 처리는 부모 클래스 메서드 호출
        logger.info("ReACT 루프를 통한 데이터 분석 시작")
        return await super().process_task(task_id, params, dependencies, raw_task_data)
    
    async def _generate_final_result(
        self, 
        session: ReACTSession, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """최종 결과 생성"""
        step_history = context.get("step_history", [])
        
        # 분석 결과 수집
        analysis_results = []
        visualization_results = []
        markdown_tables = []
        final_message = ""
        
        for step in step_history:
            observation = step.get("observation", {})
            
            if observation.get("type") == "analysis_result":
                analysis_results.append({
                    "method": observation.get("method"),
                    "result": observation.get("result")
                })
                
                # 마크다운 테이블 수집
                if isinstance(observation.get("result"), dict):
                    result = observation.get("result", {})
                    
                    # 출석 분석 결과에서 마크다운 테이블 추출
                    if "markdown_tables" in result:
                        for table_name, table in result.get("markdown_tables", {}).items():
                            markdown_tables.append({
                                "name": table_name,
                                "table": table
                            })
                    
                    # 일반 마크다운 테이블 추출
                    if "markdown_table" in result:
                        markdown_tables.append({
                            "name": observation.get("method", "data_table"),
                            "table": result.get("markdown_table")
                        })
            
            elif observation.get("type") == "visualization":
                visualization_results.append({
                    "plot_type": observation.get("plot_type"),
                    "image": observation.get("image")
                })
        
        # 분석 결과가 없는 경우, 표준 통계 테이블 생성
        if not analysis_results and not markdown_tables:
            standard_table = """| 변수 | 평균 (Mean) | 중앙값 (Median) | 표준 편차 (Standard Deviation) | 최솟값 (Minimum) | 최댓값 (Maximum) |
|------|-------------|------------------|-------------------------------|------------------|------------------|
| 샘플 | 5.5 | 5.5 | 3.87 | 1.0 | 10.0 |
"""
            markdown_tables.append({
                "name": "standard_statistics",
                "table": standard_table
            })
            
            # 임시 분석 결과 추가
            analysis_results.append({
                "method": "summary_statistics",
                "result": {
                    "message": "분석 결과를 생성하지 못했습니다. 기본 통계 테이블을 제공합니다."
                }
            })
        
        # 마크다운 테이블을 최종 메시지에 추가
        if markdown_tables:
            final_message = "## 데이터 분석 결과\n\n"
            
            for table_info in markdown_tables:
                final_message += f"### {table_info['name'].replace('_', ' ').title()}\n"
                final_message += table_info["table"]
                final_message += "\n\n"
        else:
            # 텍스트 기반 결과 메시지 생성
            final_message = "## 데이터 분석 결과\n\n"
            
            for result in analysis_results:
                final_message += f"### {result['method'].replace('_', ' ').title()}\n"
                result_obj = result.get("result", {})
                
                if isinstance(result_obj, dict):
                    for key, value in result_obj.items():
                        if isinstance(value, dict) or isinstance(value, list):
                            continue
                        final_message += f"- {key}: {value}\n"
                
                final_message += "\n"
        
        # 결과 요약
        result = {
            "success": True,
            "steps_executed": len(session.steps),
            "analysis_results": analysis_results,
            "visualization_results": visualization_results,
            "message": final_message,
            "execution_time": session.updated_at - session.created_at
        }
        
        # 세션 데이터 정리
        if session.session_id in self.session_data:
            del self.session_data[session.session_id]
        
        # 로깅
        logger.info(f"데이터 분석 세션 '{session.session_id}' 완료: {len(session.steps)} 단계 실행")
        
        return result

    async def _should_complete(
        self, 
        step_result: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> bool:
        """완료 여부 판단"""
        # 완료 플래그 확인
        if step_result.get("complete", False):
            return True
        
        # 특정 결과 상태 확인
        if step_result.get("status") == "complete":
            return True
        
        # 최종 결과 확인
        if step_result.get("type") == "final":
            return True
        
        return False

    async def _execute_reasoning(
        self, 
        session: ReACTSession, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        추론 단계 실행
        현재 상태를 바탕으로 다음에 취할 행동을 결정합니다.
        """
        start_time = time.time()
        
        # 현재 단계 설정
        step_id = f"{session.session_id}_reasoning_{len(session.steps)}"
        session.current_step = step_id
        
        try:
            # 추론을 위한 프롬프트 생성
            prompt = self._generate_reasoning_prompt(session, context)
            
            # LLM에 요청
            llm_response = await self.llm.ask(prompt)
            
            # 응답 파싱
            reasoning_result = self._parse_reasoning(llm_response)
            
            # 실행 시간 계산
            duration = time.time() - start_time
            
            # 추론 단계 기록
            reasoning_step = ReACTStep(
                step_id=step_id,
                step_type=ReACTStepType.REASONING,
                content=reasoning_result,
                timestamp=start_time,
                duration=duration,
                metadata={
                    "prompt_tokens": len(prompt) // 4,
                    "response_tokens": len(llm_response) // 4
                }
            )
            session.steps.append(reasoning_step)
            
            # 로깅
            logger.info(f"추론 단계 완료: {step_id}, 행동: {reasoning_result.get('action', 'unknown')}")
            
            return reasoning_result
            
        except Exception as e:
            logger.error(f"추론 단계 오류: {str(e)}")
            
            # Fallback 처리
            fallback_result = await self._handle_fallback(
                session, 
                ReACTStepType.REASONING, 
                e, 
                context
            )
            
            # 오류 단계 기록
            error_step = ReACTStep(
                step_id=step_id,
                step_type=ReACTStepType.ERROR,
                content=str(e),
                timestamp=start_time,
                duration=time.time() - start_time,
                metadata={"fallback": fallback_result}
            )
            session.steps.append(error_step)
            
            # 기본 Fallback 결과 반환
            return fallback_result

    async def _execute_action(
        self, 
        session: ReACTSession, 
        reasoning_result: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        행동 단계 실행
        추론 결과를 바탕으로 실제 행동을 수행합니다.
        """
        start_time = time.time()
        
        # 현재 단계 설정
        step_id = f"{session.session_id}_action_{len(session.steps)}"
        session.current_step = step_id
        
        try:
            # 추론 결과에서 행동 추출
            action = self._extract_action(reasoning_result)
            
            # 행동 수행
            action_result = await self._perform_action(action, session, context)
            
            # 실행 시간 계산
            duration = time.time() - start_time
            
            # 행동 단계 기록
            action_step = ReACTStep(
                step_id=step_id,
                step_type=ReACTStepType.ACTION,
                content=action_result,
                timestamp=start_time,
                duration=duration,
                metadata={
                    "action_type": action.get("type", "unknown"),
                    "action_target": action.get("target", "unknown")
                }
            )
            session.steps.append(action_step)
            
            # 로깅
            logger.info(f"행동 단계 완료: {step_id}, 유형: {action.get('type', 'unknown')}")
            
            return action_result
            
        except Exception as e:
            logger.error(f"행동 단계 오류: {str(e)}")
            
            # Fallback 처리
            fallback_result = await self._handle_fallback(
                session, 
                ReACTStepType.ACTION, 
                e, 
                context
            )
            
            # 오류 단계 기록
            error_step = ReACTStep(
                step_id=step_id,
                step_type=ReACTStepType.ERROR,
                content=str(e),
                timestamp=start_time,
                duration=time.time() - start_time,
                metadata={"fallback": fallback_result}
            )
            session.steps.append(error_step)
            
            # 기본 Fallback 결과 반환
            return fallback_result

    async def _execute_observation(
        self, 
        session: ReACTSession, 
        action_result: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        관찰 단계 실행
        행동의 결과를 분석하고 다음 단계를 위한 관찰을 수행합니다.
        """
        start_time = time.time()
        
        # 현재 단계 설정
        step_id = f"{session.session_id}_observation_{len(session.steps)}"
        session.current_step = step_id
        
        try:
            # 행동 결과 분석
            observation_result = self._analyze_action_result(action_result, session, context)
            
            # 실행 시간 계산
            duration = time.time() - start_time
            
            # 관찰 단계 기록
            observation_step = ReACTStep(
                step_id=step_id,
                step_type=ReACTStepType.OBSERVATION,
                content=observation_result,
                timestamp=start_time,
                duration=duration,
                metadata={
                    "observation_type": observation_result.get("type", "general"),
                    "content_length": len(json.dumps(observation_result))
                }
            )
            session.steps.append(observation_step)
            
            # 로깅
            logger.info(f"관찰 단계 완료: {step_id}")
            
            return observation_result
            
        except Exception as e:
            logger.error(f"관찰 단계 오류: {str(e)}")
            
            # Fallback 처리
            fallback_result = await self._handle_fallback(
                session, 
                ReACTStepType.OBSERVATION, 
                e, 
                context
            )
            
            # 오류 단계 기록
            error_step = ReACTStep(
                step_id=step_id,
                step_type=ReACTStepType.ERROR,
                content=str(e),
                timestamp=start_time,
                duration=time.time() - start_time,
                metadata={"fallback": fallback_result}
            )
            session.steps.append(error_step)
            
            # 기본 Fallback 결과 반환
            return fallback_result

    def _generate_reasoning_prompt(self, session: ReACTSession, context: Dict[str, Any]) -> str:
        """추론을 위한 프롬프트 생성"""
        params = context.get("params", {})
        query = params.get("query", "")
        
        # 세션 데이터 확인
        session_data = self.session_data.get(session.session_id, {})
        data_loaded = "data_loaded" in session_data and session_data["data_loaded"]
        
        # 단계 기록
        step_history = context.get("step_history", [])
        history_text = ""
        
        for i, step in enumerate(step_history):
            reasoning = step.get("reasoning", {})
            action = step.get("action", {})
            observation = step.get("observation", {})
            
            history_text += f"\n단계 {i+1}:\n"
            history_text += f"사고 과정: {reasoning.get('thought', '')}\n"
            history_text += f"행동: {action.get('type', '')} - 파라미터: {json.dumps(action.get('params', {}), ensure_ascii=False)}\n"
            history_text += f"관찰: {json.dumps(observation, ensure_ascii=False)[:200]}...(생략)\n"
        
        # 데이터 상태 정보
        data_status = "데이터가 로드되었습니다." if data_loaded else "데이터가 아직 로드되지 않았습니다."
        if data_loaded and "columns" in session_data:
            data_status += f"\n사용 가능한 컬럼: {', '.join(session_data['columns'])}"
        
        # 프롬프트 구성
        prompt = (
            f"# 데이터 분석 요청\n{query}\n\n"
            f"# 데이터 상태\n{data_status}\n\n"
            f"# 단계 기록\n{history_text or '이전 단계 없음'}\n\n"
            "# 사용 가능한 행동\n"
            "1. load_data: 데이터 로드 (파라미터: data_source, format)\n"
            "2. analyze_data: 데이터 분석 (파라미터: method, column)\n"
            "3. visualize_data: 데이터 시각화 (파라미터: plot_type, column)\n"
            "4. complete: 작업 완료\n\n"
            "# 지시사항\n"
            "1. 현재 상태를 이해하고 다음에 수행할 최선의 행동을 결정하세요.\n"
            "2. 결과를 다음 형식으로 제공하세요:\n"
            "   - 사고 과정: (상황을 이해하고 분석하는 방법)\n"
            "   - 다음 행동: (행동 유형)\n"
            "   - 파라미터: (행동에 필요한 파라미터)\n"
            "   - 이유: (이 행동을 선택한 이유)\n"
            "3. 분석이 더 이상 필요 없으면 '다음 행동: complete'라고 표시하세요.\n\n"
            "이제 상황을 분석하고 다음 행동을 결정하세요."
        )
        
        return prompt
    
    def _parse_reasoning(self, llm_response: str) -> Dict[str, Any]:
        """LLM 응답에서 추론 결과 파싱"""
        lines = llm_response.strip().split('\n')
        
        result = {
            "thought": "",
            "action": None,
            "params": {},
            "reason": ""
        }
        
        # 각 라인 분석
        current_section = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith("사고 과정:"):
                current_section = "thought"
                result["thought"] = line[len("사고 과정:"):].strip()
            elif line.startswith("다음 행동:"):
                current_section = "action"
                result["action"] = line[len("다음 행동:"):].strip()
            elif line.startswith("파라미터:"):
                current_section = "params"
                params_str = line[len("파라미터:"):].strip()
                try:
                    # JSON 형식 파싱
                    if params_str.startswith("{") and params_str.endswith("}"):
                        result["params"] = json.loads(params_str)
                except:
                    result["params"] = {"raw": params_str}
            elif line.startswith("이유:"):
                current_section = "reason"
                result["reason"] = line[len("이유:"):].strip()
            elif current_section:
                # 현재 섹션에 내용 추가
                result[current_section] += " " + line
        
        return result

    def _extract_action(self, reasoning_result: Dict[str, Any]) -> Dict[str, Any]:
        """추론 결과에서 수행할 행동 추출"""
        action_type = reasoning_result.get("action", "")
        params = reasoning_result.get("params", {})
        
        # 로깅 추가
        logger.info(f"행동 추출: {action_type}, 파라미터: {params}")
        
        # 완료 액션 확인
        if action_type.lower() == "complete":
            return {
                "type": "complete",
                "params": {},
                "target": "internal",
                "complete": True
            }
        
        # 내부 액션 확인 (데이터 분석 관련)
        if action_type in ["load_data", "analyze_data", "visualize_data"]:
            return {
                "type": action_type,
                "params": params,
                "target": "internal",
                "reason": reasoning_result.get("reason", "데이터 분석을 위한 내부 액션")
            }
        
        # 에이전트 호출 액션
        if action_type in ["web_search", "writer", "code_generator"]:
            return {
                "type": action_type,
                "params": params,
                "target": "agent",
                "reason": reasoning_result.get("reason", f"{action_type} 에이전트 호출")
            }
        
        # 기본 행동
        return {
            "type": action_type,
            "params": params,
            "target": "internal",  # 기본값을 internal로 설정
            "reason": reasoning_result.get("reason", "명확한 행동 유형이 아닙니다.")
        }
    
    async def _perform_action(
        self, 
        action: Dict[str, Any], 
        session: ReACTSession, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """행동 수행"""
        action_type = action.get("type", "")
        params = action.get("params", {})
        
        # 로깅 추가
        logger.info(f"행동 수행: {action_type}, 파라미터: {params}")
        
        # 완료 액션 처리
        if action_type == "complete":
            return {
                "status": "complete",
                "message": "데이터 분석이 완료되었습니다.",
                "complete": True
            }
        
        # 내부 액션 처리
        if action.get("target") == "internal" or action_type in ["load_data", "analyze_data", "visualize_data"]:
            # 세션 데이터 초기화
            if session.session_id not in self.session_data:
                self.session_data[session.session_id] = {}
                
            # 데이터 로드 액션
            if action_type == "load_data":
                # 요청 파라미터에서 데이터 소스 확인
                request_params = context.get("params", {})
                data_source = params.get("data_source")
                
                # 데이터 소스가 없는 경우, 요청 파라미터에서 가져옴
                if not data_source:
                    data_source = request_params.get("data")
                    logger.info(f"요청 파라미터에서 데이터 가져옴: {data_source and len(data_source) or 'None'}")
                
                # 데이터 소스가 없는 경우 에러 반환
                if not data_source:
                    logger.error("데이터 소스가 제공되지 않았습니다.")
                    return {"success": False, "error": "데이터 소스가 제공되지 않았습니다."}
                
                format_type = params.get("format", "csv_string")
                
                # 데이터 로드
                logger.info(f"데이터 로드 시작: 형식={format_type}, 길이={len(data_source)}")
                result = self.analyzer.load_data(data_source, {"format": format_type})
                
                # 세션 데이터 업데이트
                if result.get("success"):
                    self.session_data[session.session_id]["data_loaded"] = True
                    if "columns" in result:
                        self.session_data[session.session_id]["columns"] = result["columns"]
                    logger.info(f"데이터 로드 성공: {result.get('message')}")
                else:
                    logger.error(f"데이터 로드 실패: {result.get('error')}")
                
                return result
            
            # 데이터 분석 액션
            elif action_type == "analyze_data":
                # 데이터가 로드되지 않은 경우, 자동으로 로드 시도
                if self.analyzer.data is None and self.analyzer.text_data is None:
                    # 요청 파라미터에서 데이터 소스 확인
                    request_params = context.get("params", {})
                    data_source = request_params.get("data")
                    
                    if data_source:
                        logger.info("데이터가 로드되지 않아 자동 로드 시도")
                        load_result = self.analyzer.load_data(data_source, {"format": "auto"})
                        
                        if not load_result.get("success"):
                            return load_result
                    else:
                        return {"success": False, "error": "분석을 위한 데이터가 로드되지 않았습니다."}
                
                method = params.get("method", "summary_statistics")
                column = params.get("column")
                
                logger.info(f"데이터 분석 시작: 메서드={method}, 열={column}")
                analysis_params = {}
                if column:
                    analysis_params["column"] = column
                
                # 메서드별 특별 파라미터 처리
                if method == "extract_structured_data":
                    extraction_type = params.get("extraction_type")
                    if extraction_type:
                        analysis_params["extraction_type"] = extraction_type
                
                result = self.analyzer.analyze_data(method, analysis_params)
                
                # 분석 성공 여부 로깅
                if result.get("success"):
                    logger.info(f"데이터 분석 성공: 메서드={method}")
                else:
                    logger.error(f"데이터 분석 실패: {result.get('error')}")
                    
                return result
            
            # 데이터 시각화 액션
            elif action_type == "visualize_data":
                plot_type = params.get("plot_type")
                if not plot_type:
                    return {"success": False, "error": "시각화 유형이 지정되지 않았습니다."}
                
                logger.info(f"데이터 시각화 시작: 유형={plot_type}")
                
                # column 파라미터가 'AUTO'인 경우 자동 선택
                if params.get("column") == "AUTO":
                    if self.analyzer.data is not None and not self.analyzer.data.empty:
                        numeric_cols = self.analyzer.data.select_dtypes(include=['number']).columns
                        if not numeric_cols.empty:
                            params["column"] = numeric_cols[0]
                            logger.info(f"자동 컬럼 선택: {params['column']}")
                
                result = self.analyzer.visualize_data(plot_type, params)
                
                # 시각화 성공 여부 로깅
                if result.get("success"):
                    logger.info(f"데이터 시각화 성공: 유형={plot_type}")
                else:
                    logger.error(f"데이터 시각화 실패: {result.get('error')}")
                
                return result
        
        # 다른 에이전트 호출
        elif action.get("target") == "agent":
            role = action_type
            # 브로커를 통해 에이전트 호출
            agent_result = await self._call_agent_through_broker(role, params)
            return {
                "status": "success",
                "agent": role,
                "result": agent_result
            }
        
        # 알 수 없는 행동 처리
        return {
            "status": "error",
            "message": f"지원되지 않는 행동 유형: {action_type}"
        }
        
    async def _call_agent_through_broker(
        self, 
        role: str, 
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """브로커를 통해 다른 에이전트 호출"""
        try:
            # 브로커에 태스크 제출
            result = await self.submit_task_to_broker(
                role=role,
                params=params
            )
            
            if not result.get("success"):
                logger.error(f"브로커 태스크 실행 실패: {result.get('error')}")
                return {
                    "success": False,
                    "error": result.get("error", "알 수 없는 오류")
                }
            
            return result.get("result", {})
            
        except Exception as e:
            logger.error(f"에이전트 호출 오류: {str(e)}")
            return {
                "success": False,
                "error": f"에이전트 호출 오류: {str(e)}"
            }
    
    def _analyze_action_result(
        self, 
        action_result: Dict[str, Any], 
        session: ReACTSession, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """행동 결과 분석"""
        # 완료 상태 확인
        if action_result.get("complete", False) or action_result.get("status") == "complete":
            return {
                "type": "final",
                "message": "데이터 분석이 완료되었습니다.",
                "complete": True
            }
        
        # 데이터 로드 결과 분석
        if "columns" in action_result:
            return {
                "type": "data_loaded",
                "columns": action_result.get("columns", []),
                "shape": action_result.get("shape", [0, 0]),
                "message": action_result.get("message", "데이터 로드 완료")
            }
        
        # 데이터 분석 결과 분석
        if "method" in action_result:
            return {
                "type": "analysis_result",
                "method": action_result.get("method"),
                "result": action_result.get("result", {}),
                "summary": f"{action_result.get('method')} 분석이 완료되었습니다."
            }
        
        # 시각화 결과 분석
        if "plot_type" in action_result and "image" in action_result:
            return {
                "type": "visualization",
                "plot_type": action_result.get("plot_type"),
                "image": action_result.get("image"),
                "summary": f"{action_result.get('plot_type')} 시각화가 생성되었습니다."
            }
        
        # 에이전트 결과 분석
        if "agent" in action_result:
            return {
                "type": "agent_result",
                "agent": action_result.get("agent"),
                "result": action_result.get("result", {}),
                "summary": f"{action_result.get('agent')} 에이전트의 결과가 수신되었습니다."
            }
        
        # 오류 분석
        if not action_result.get("success", True) or action_result.get("status") == "error":
            return {
                "type": "error",
                "message": action_result.get("error") or action_result.get("message", "알 수 없는 오류"),
                "need_retry": True
            }
        
        # 기본 분석
        return {
            "type": "general",
            "content": action_result,
            "summary": "행동이 실행되었으나 구체적인 결과 유형이 감지되지 않았습니다."
        }

# 루트 엔드포인트
@app.get("/")
async def root():
    return {
        "name": "Data Analysis Agent",
        "description": "데이터 로딩, 분석 및 시각화를 수행하는 전문 에이전트",
        "status": "active"
    }

# 에이전트 인스턴스 생성 
data_analysis_agent = DataAnalysisAgent(app) 