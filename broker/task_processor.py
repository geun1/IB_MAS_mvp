async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    태스크 처리 및 에이전트 호출
    
    Args:
        task_data: 태스크 데이터
        
    Returns:
        처리 결과
    """
    task_id = task_data.get("task_id")
    role = task_data.get("role")
    params = task_data.get("params", {})
    context = task_data.get("context", {})
    
    logger.info(f"태스크 처리 시작: {task_id} (역할: {role})")
    
    # 의존성 결과 처리 로깅 추가
    depends_results = context.get("depends_results", [])
    if depends_results:
        logger.info(f"태스크 {task_id}에 {len(depends_results)}개의 의존성 결과가 포함됨")
    
    # 에이전트 선택
    agent = await self.agent_selector.select_agent(role)
    if not agent:
        logger.error(f"역할 '{role}'에 적합한 에이전트를 찾을 수 없음")
        return {
            "status": "failed",
            "error": f"역할 '{role}'에 적합한 에이전트를 찾을 수 없습니다",
            "task_id": task_id
        }
    
    # 에이전트 호출 데이터 준비
    agent_request = {
        "task_id": task_id,
        "params": params,
        "depends_results": depends_results  # 의존성 결과 전달
    }
    
    # 에이전트 호출
    try:
        result = await self.agent_client.call_agent(
            agent["endpoint"], 
            agent["agent_id"],
            agent_request
        )
        
        logger.info(f"태스크 {task_id} 완료: {result.get('status', 'unknown')}")
        return {
            "status": "completed",
            "result": result,
            "agent_id": agent["agent_id"],
            "task_id": task_id
        }
        
    except Exception as e:
        logger.error(f"태스크 {task_id} 처리 중 오류: {str(e)}")
        return {
            "status": "failed",
            "error": str(e),
            "task_id": task_id
        } 