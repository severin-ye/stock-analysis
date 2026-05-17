"""配置模块 — 从环境变量或 opencode.jsonc 读取 LLM 配置

支持:
  - 环境变量优先: LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
  - opencode.jsonc fallback (自动解析 JSONC 注释)
  - 百炼 Token Plan 统一 API / DeepSeek 直连
"""

import json
import os
import re
from pathlib import Path

OPENCODE_CONFIG = Path.home() / '.config' / 'opencode' / 'opencode.jsonc'


def _read_secret(path: str) -> str:
    filepath = Path(path.replace('{file:', '').rstrip('}')).expanduser()
    try:
        return filepath.read_text().strip()
    except FileNotFoundError:
        raise RuntimeError(f"密钥文件不存在: {filepath}")


def load_config() -> dict:
    try:
        text = OPENCODE_CONFIG.read_text(encoding='utf-8')
    except FileNotFoundError:
        return {}
    lines = []
    for line in text.splitlines():
        idx = line.find('//')
        if idx >= 0:
            before = line[:idx]
            quote_count = before.count('"') - before.count('\\"')
            if quote_count % 2 == 0:
                line = line[:idx]
        lines.append(line)
    text = '\n'.join(lines)
    text = re.sub(r'/\*[\s\S]*?\*/', '', text)
    return json.loads(text)


PREFERRED_LLM_ORDER = ['deepseek-v4-pro', 'deepseek-v4-flash', 'deepseek-v3.2', 'qwen3.6-plus']


def get_llm_config() -> dict:
    """获取 LLM 配置 — 环境变量优先，opencode.jsonc 次之"""
    api_key = os.environ.get('LLM_API_KEY')
    base_url = os.environ.get('LLM_BASE_URL')
    model = os.environ.get('LLM_MODEL')

    if api_key and base_url:
        if not base_url.endswith('/v1'):
            base_url = base_url.rstrip('/') + '/v1'
        return {
            'api_key': api_key,
            'base_url': base_url,
            'model': model or 'deepseek-v4-pro',
            'provider_model_id': model or 'deepseek-v4-pro',
            'provider_name': 'env',
        }

    config = load_config()
    providers = config.get('provider', {})

    for prov_name, prov_data in providers.items():
        options = prov_data.get('options', {})
        base_url = options.get('baseURL', '')
        api_key_raw = options.get('apiKey', '')
        if not base_url or not api_key_raw:
            continue

        if api_key_raw.startswith('{file:'):
            api_key = _read_secret(api_key_raw)
        else:
            api_key = api_key_raw

        if not base_url.endswith('/v1'):
            base_url = base_url.rstrip('/') + '/v1'

        models = prov_data.get('models', {})
        for preferred in PREFERRED_LLM_ORDER:
            if preferred in models:
                return {
                    'api_key': api_key,
                    'base_url': base_url,
                    'model': preferred,
                    'provider_model_id': preferred,
                    'provider_name': prov_name,
                }

    raise RuntimeError(
        "未找到可用 LLM 模型的 provider 配置。\n"
        "请设置环境变量 LLM_API_KEY + LLM_BASE_URL，\n"
        "或配置 ~/.config/opencode/opencode.jsonc"
    )
