def create_openai_client(base_url: str, api_key: str):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("请先安装 openai：pip install openai") from exc
    return OpenAI(base_url=base_url, api_key=api_key)

