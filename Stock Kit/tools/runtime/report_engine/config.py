"""配置模块 — 从 opencode.json 读取 LLM 配置"""

import json
from pathlib import Path

OPENCODE_CONFIG = Path.home() / '.config' / 'opencode' / 'opencode.json'


def _read_secret(path: str) -> str:
    """读取 {file:path} 格式的密钥"""
    filepath = Path(path.replace('{file:', '').rstrip('}')).expanduser()
    return filepath.read_text().strip()


def load_config() -> dict:
    with open(OPENCODE_CONFIG) as f:
        return json.load(f)


def get_deepseek_config() -> dict:
    """获取 DeepSeek API 配置"""
    config = load_config()
    provider = config['provider'].get('deepseek-api', {})

    options = provider.get('options', {})
    api_key_raw = options.get('apiKey', '')
    if api_key_raw.startswith('{file:'):
        api_key = _read_secret(api_key_raw)
    else:
        api_key = api_key_raw

    base_url = options.get('baseURL', 'https://api.deepseek.com')
    if not base_url.endswith('/v1'):
        base_url = base_url.rstrip('/') + '/v1'

    model_id = config.get('model', 'deepseek-api/deepseek-v4-pro')
    model_name = model_id.split('/')[-1]

    # DeepSeek API 模型名映射
    model_map = {
        'deepseek-v4-pro': 'deepseek-chat',
        'deepseek-v4-flash': 'deepseek-chat',
        'deepseek-v3.2': 'deepseek-chat',
    }

    return {
        'api_key': api_key,
        'base_url': base_url,
        'model': model_map.get(model_name, 'deepseek-chat'),
        'provider_model_id': model_name,
    }
