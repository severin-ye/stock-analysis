"""OpenCode LLM IPC 客户端

通过文件系统 + stdout 标记实现 Pipeline 与 OpenCode Agent 的进程间通信。

协议:
  1. Pipeline 将 LLM 请求写入 .sisyphus/llm_requests/{request_id}.json
  2. Pipeline 向 stdout 打印标记: __OPENCODE_LLM_REQUEST__:{request_id}
  3. OpenCode Agent 捕获标记，读取请求文件，调用 LLM
  4. OpenCode Agent 将响应写入 .sisyphus/llm_responses/{request_id}.json
  5. Pipeline 轮询等待响应文件，读取后删除

回退机制:
  如果 OpenCode Agent 在超时时间内未响应，自动 fallback 到直接 API 调用。
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# 请求/响应目录
BASE_DIR = Path(os.environ.get('STOCK_ANALYSIS_HOME', str(Path(__file__).resolve().parent.parent.parent)))
LLM_REQ_DIR = BASE_DIR / '.sisyphus' / 'llm_requests'
LLM_RESP_DIR = BASE_DIR / '.sisyphus' / 'llm_responses'

# 确保目录存在
LLM_REQ_DIR.mkdir(parents=True, exist_ok=True)
LLM_RESP_DIR.mkdir(parents=True, exist_ok=True)

# stdout 标记前缀
REQUEST_MARKER = "__OPENCODE_LLM_REQUEST__"


class OpenCodeLLMClient:
    """通过 IPC 调用 OpenCode Agent 的 LLM"""

    def __init__(self, timeout: int = 300, poll_interval: float = 1.0):
        """
        Args:
            timeout: 等待 OpenCode Agent 响应的最大秒数（默认 5 分钟）
            poll_interval: 轮询间隔（秒）
        """
        self.timeout = timeout
        self.poll_interval = poll_interval

    def invoke(self, prompt: str, model: str = "deepseek-v4-pro", temperature: float = 0.1) -> str:
        """发送 LLM 请求并等待响应

        流程:
          1. 生成唯一 request_id
          2. 将请求写入请求文件
          3. 打印 stdout 标记
          4. 轮询等待响应文件
          5. 读取响应并清理文件

        Args:
            prompt: 发送给 LLM 的完整 prompt
            model: 模型名称
            temperature: 温度参数

        Returns:
            LLM 生成的文本内容

        Raises:
            TimeoutError: 如果 OpenCode Agent 在超时时间内未响应
        """
        request_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # 1. 写入请求文件
        req_file = LLM_REQ_DIR / f"{request_id}.json"
        req_data = {
            "request_id": request_id,
            "timestamp": time.time(),
            "model": model,
            "temperature": temperature,
            "prompt": prompt,
            "prompt_length": len(prompt),
        }
        req_file.write_text(json.dumps(req_data, ensure_ascii=False, indent=2), encoding='utf-8')

        # 2. 打印 stdout 标记（供 OpenCode Agent 捕获）
        marker = f"{REQUEST_MARKER}:{request_id}"
        print(f"\n{marker}\n", flush=True)

        # 3. 轮询等待响应文件
        resp_file = LLM_RESP_DIR / f"{request_id}.json"
        start_time = time.time()
        elapsed = 0.0

        while elapsed < self.timeout:
            if resp_file.exists():
                try:
                    resp_data = json.loads(resp_file.read_text(encoding='utf-8'))
                    content = resp_data.get('content', '')

                    # 清理文件
                    req_file.unlink(missing_ok=True)
                    resp_file.unlink(missing_ok=True)

                    return content
                except (json.JSONDecodeError, KeyError) as e:
                    raise RuntimeError(f"OpenCode LLM 响应格式错误: {e}")

            time.sleep(self.poll_interval)
            elapsed = time.time() - start_time

        # 超时：清理文件并抛出异常
        req_file.unlink(missing_ok=True)
        raise TimeoutError(
            f"OpenCode LLM 响应超时 ({self.timeout}s)。\n"
            f"请求文件: {req_file}\n"
            f"OpenCode Agent 未在超时时间内处理该请求。\n"
            f"可能原因:\n"
            f"  1. OpenCode Agent 未运行或未捕获 stdout 标记\n"
            f"  2. 标记格式不匹配（期望: {REQUEST_MARKER}:{request_id}）\n"
            f"  3. 网络问题导致 LLM 调用失败\n"
            f"解决方式:\n"
            f"  - 不用 --use-opencode-llm 参数，直接调用 API\n"
            f"  - 或检查 OpenCode Agent 是否正确配置"
        )

    def is_available(self) -> bool:
        """检查 OpenCode LLM 模式是否可用

        通过检查 stdout 是否为 tty 来判断是否运行在交互式环境中。
        如果是非交互式环境（如 CI），OpenCode Agent 可能无法捕获 stdout。
        """
        return sys.stdout.isatty()


def create_llm_client(use_opencode: bool = False, timeout: int = 300):
    """创建 LLM 客户端

    Args:
        use_opencode: 是否使用 OpenCode IPC 模式
        timeout: OpenCode 模式的超时时间

    Returns:
        如果 use_opencode=True 返回 OpenCodeLLMClient
        否则返回 None（使用直接 API 调用）
    """
    if use_opencode:
        client = OpenCodeLLMClient(timeout=timeout)
        if not client.is_available():
            import warnings
            warnings.warn(
                "--use-opencode-llm 已启用，但当前环境非交互式（stdout 不是 tty）。\n"
                "OpenCode Agent 可能无法捕获 stdout 标记，将自动 fallback 到直接 API 调用。",
                RuntimeWarning
            )
            return None
        return client
    return None