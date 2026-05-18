"""配置模块 — 从环境变量或 opencode.jsonc 读取 LLM 配置

支持:
  - 环境变量优先: LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
  - opencode.jsonc fallback (自动解析 JSONC 注释)
  - 百炼 Token Plan 统一 API / DeepSeek 直连

架构说明:
  本项目作为 OpenCode Agent 的插件运行时，默认复用 OpenCode 的 LLM 配置
  (~/.config/opencode/opencode.jsonc)。如果该配置不存在，才会尝试环境变量。
  这是双层架构设计：OpenCode Agent 负责推理决策，本项目的 LLM 仅用于
  将真实数据润色为中文叙述文本（反幻觉）。
"""

import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger("config")

OPENCODE_CONFIG = Path.home() / ".config" / "opencode" / "opencode.jsonc"


def _read_secret(path: str) -> str:
    filepath = Path(path.replace("{file:", "").rstrip("}")).expanduser()
    try:
        return filepath.read_text().strip()
    except FileNotFoundError:
        raise RuntimeError(f"密钥文件不存在: {filepath}")


def load_config() -> dict:
    try:
        text = OPENCODE_CONFIG.read_text(encoding="utf-8")
        logger.debug(f"已读取 OpenCode 配置: {OPENCODE_CONFIG}")
    except FileNotFoundError:
        logger.debug(f"OpenCode 配置文件不存在: {OPENCODE_CONFIG}")
        return {}
    lines = []
    for line in text.splitlines():
        idx = line.find("//")
        if idx >= 0:
            before = line[:idx]
            quote_count = before.count('"') - before.count('\\"')
            if quote_count % 2 == 0:
                line = line[:idx]
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    result: dict = json.loads(text)
    return result


PREFERRED_LLM_ORDER = ["kimi-k2.6", "kimi-k2.5", "deepseek-v4-pro", "deepseek-v4-flash", "deepseek-v3.2", "qwen3.6-plus"]

# 支持通过环境变量覆盖模型选择
# 用法: export LLM_MODEL=kimi-k2 或 export LLM_MODEL=deepseek-v4-pro
ENV_OVERRIDES = {
    "model": os.environ.get("LLM_MODEL"),
    "base_url": os.environ.get("LLM_BASE_URL"),
    "api_key": os.environ.get("LLM_API_KEY"),
}


def get_llm_config() -> dict:
    """获取 LLM 配置 — 环境变量优先，opencode.jsonc 次之

    搜索顺序:
      1. 环境变量 LLM_API_KEY + LLM_BASE_URL
      2. ~/.config/opencode/opencode.jsonc (OpenCode 配置)

    如果两者都未找到，抛出 RuntimeError 并说明配置方式。
    """
    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL")
    model = os.environ.get("LLM_MODEL")

    if api_key and base_url:
        logger.info("使用环境变量 LLM 配置")
        if not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
        return {
            "api_key": api_key,
            "base_url": base_url,
            "model": model or "deepseek-v4-pro",
            "provider_model_id": model or "deepseek-v4-pro",
            "provider_name": "env",
        }

    logger.info(f"尝试读取 OpenCode 配置: {OPENCODE_CONFIG}")
    config = load_config()

    if not config:
        raise RuntimeError(
            f"未找到 LLM 配置。\n\n"
            f"本项目作为 OpenCode Agent 插件运行时，默认复用 OpenCode 的 LLM 配置。\n"
            f"当前尝试读取: {OPENCODE_CONFIG} (未找到)\n\n"
            f"解决方式 (任选其一):\n"
            f"  1. 确保 OpenCode 已配置 LLM (opencode.jsonc 存在且包含 provider 配置)\n"
            f"  2. 创建 .env 文件并设置 LLM_API_KEY + LLM_BASE_URL:\n"
            f"     cp .env.example .env  # 然后编辑填入你的 API 密钥\n"
            f"  3. 直接设置环境变量:\n"
            f"     export LLM_API_KEY=sk-xxx\n"
            f"     export LLM_BASE_URL=https://api.deepseek.com"
        )

    providers = config.get("provider", {})

    if not providers:
        raise RuntimeError(
            f"OpenCode 配置文件存在，但未找到 provider 配置。\n请检查 {OPENCODE_CONFIG} 是否包含 'provider' 字段。"
        )

    for prov_name, prov_data in providers.items():
        options = prov_data.get("options", {})
        base_url = options.get("baseURL", "")
        api_key_raw = options.get("apiKey", "")
        if not base_url or not api_key_raw:
            continue

        if api_key_raw.startswith("{file:"):
            api_key = _read_secret(api_key_raw)
        else:
            api_key = api_key_raw

        if not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"

        models = prov_data.get("models", {})
        
        # 检查是否有环境变量覆盖模型选择
        env_model = os.environ.get("LLM_MODEL")
        if env_model and env_model in models:
            logger.info(f"使用环境变量指定的模型: {env_model} (provider: {prov_name})")
            return {
                "api_key": api_key,
                "base_url": base_url,
                "model": env_model,
                "provider_model_id": env_model,
                "provider_name": prov_name,
            }
        
        for preferred in PREFERRED_LLM_ORDER:
            if preferred in models:
                logger.info(f"使用 OpenCode provider: {prov_name}, model: {preferred}")
                return {
                    "api_key": api_key,
                    "base_url": base_url,
                    "model": preferred,
                    "provider_model_id": preferred,
                    "provider_name": prov_name,
                }

    raise RuntimeError(
        f"OpenCode 配置中未找到支持的 LLM 模型。\n"
        f"支持的模型 (按优先级): {', '.join(PREFERRED_LLM_ORDER)}\n"
        f"请在 {OPENCODE_CONFIG} 中配置上述模型之一，"
        f"或通过环境变量 LLM_API_KEY + LLM_BASE_URL 覆盖。"
    )
