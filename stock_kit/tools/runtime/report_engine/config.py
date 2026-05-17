"""配置模块 — 从 opencode.jsonc 读取 LLM 配置

支持:
  - 百炼 Token Plan 统一 API (当前主用)
  - DeepSeek 直连 API (legacy fallback)
"""

import json
import re
from pathlib import Path

OPENCODE_CONFIG = Path.home() / '.config' / 'opencode' / 'opencode.jsonc'


def _read_secret(path: str) -> str:
    filepath = Path(path.replace('{file:', '').rstrip('}')).expanduser()
    return filepath.read_text().strip()


def load_config() -> dict:
    text = OPENCODE_CONFIG.read_text(encoding='utf-8')
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


def get_deepseek_config() -> dict:
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

    raise RuntimeError("未找到可用 LLM 模型的 provider 配置")