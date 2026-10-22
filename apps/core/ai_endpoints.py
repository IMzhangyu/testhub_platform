"""
OpenAI 兼容接口的地址构建与调用

各厂商 base_url 规范并不统一：有的以 /v1 结尾（DeepSeek、硅基流动），有的版本号在路径
中间（百度千帆 Token Plan 的 https://qianfan.baidubce.com/v2/tokenplan/personal），
甚至同一厂商的对话接口和模型列表接口拼法都不一样。因此统一按“候选地址 + 仅 404 回落”
处理，避免同一个 base_url 在不同模块里被解释成不同地址。
"""
import logging
import re
from typing import Any, Dict, List, Tuple

import requests

logger = logging.getLogger(__name__)

CHAT_COMPLETIONS = '/chat/completions'
MODELS = '/models'
KNOWN_ENDPOINTS = (CHAT_COMPLETIONS, MODELS)


def build_openai_compatible_urls(base_url: str, endpoint: str) -> List[str]:
    """返回按优先级排序的候选接口地址。"""
    normalized_base_url = base_url.rstrip('/')

    if normalized_base_url.endswith(endpoint):
        return [normalized_base_url]

    for known_endpoint in KNOWN_ENDPOINTS:
        if normalized_base_url.endswith(known_endpoint):
            normalized_base_url = normalized_base_url[:-len(known_endpoint)]
            break

    direct_url = f"{normalized_base_url}{endpoint}"
    v1_url = f"{normalized_base_url}/v1{endpoint}"

    # base_url 以版本号结尾（如 /v1、/v4）时，直接拼接即可
    if re.search(r'/v\d+/?$', normalized_base_url):
        return [direct_url]
    # 版本号出现在路径中间（如 /v2/tokenplan/personal）时，优先直接拼接，/v1 兜底
    if re.search(r'/v\d+/', normalized_base_url):
        return [direct_url, v1_url]

    return [v1_url, direct_url]


def post_with_endpoint_fallback(base_url: str, payload: Dict[str, Any], headers: Dict[str, str],
                                timeout: Any, endpoint: str = CHAT_COMPLETIONS) -> Tuple[str, 'requests.Response']:
    """按候选地址依次 POST，仅当返回 404 且仍有备用地址时才更换地址。"""
    candidates = build_openai_compatible_urls(base_url, endpoint)
    url = candidates[0]
    response = None

    for index, candidate_url in enumerate(candidates):
        url = candidate_url
        logger.info(f"发送POST请求到: {url}")
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if response.status_code == 404 and index + 1 < len(candidates):
            logger.warning(f"接口地址 {url} 返回404，改用备用地址重试")
            continue
        break

    return url, response
