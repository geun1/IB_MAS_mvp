# 에이전트 URL 구성 로직 수정
agent_base_url = f"http://{agent_info['host']}:{agent_info['port']}"
if agent_info['role'] == 'web_search':
    agent_url = f"{agent_base_url}/run"
else:
    agent_url = f"{agent_base_url}/run" 