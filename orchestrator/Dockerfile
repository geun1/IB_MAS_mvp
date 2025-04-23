FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
COPY common/ /app/common/
COPY orchestrator/ /app/orchestrator/

RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app/orchestrator

# 환경 변수 추가
ENV REGISTRY_URL=http://registry:8000
ENV BROKER_URL=http://broker:8002
ENV LLM_MODEL=gpt-4o-mini
ENV LLM_TEMPERATURE=0.7
ENV LLM_MAX_TOKENS=2048
ENV DEFAULT_TASK_TIMEOUT=300
ENV MAX_PARALLEL_TASKS=5
ENV PYTHONPATH=/app

CMD ["uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"] 