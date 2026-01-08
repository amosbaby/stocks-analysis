# volces_chat.py
import requests
import json
import re
import os
from typing import Optional
 
 
VOLCES_API_KEY = "fe1b0d9c-52a1-48ad-ba7d-caab97681998"   # 可被环境变量 VOLCES_API_KEY 覆盖
# 默认使用“模型直连”接口；如你使用 bot，请通过 VOLCES_ENDPOINT 指向 bots 接口，并设置 VOLCES_BOT_ID
ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
# MODEL = "deepseek-v3-250324"
MODEL = "deepseek-v3-2-251201" # 可被环境变量 VOLCES_MODEL 覆盖
 
 
def _is_placeholder(value: Optional[str]) -> bool:
    if not value:
        return True
    v = value.strip()
    # 常见占位符：xxxxxxxx / xxxxxxxx / xxx...
    return (set(v) == {"x"}) or (set(v.lower()) == {"x"})


def chat_volces(
    system: str,
    user: str,
    timeout: int = 30,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    endpoint: str = ENDPOINT,
) -> str:
    """
    调用火山方舟 DeepSeek 模型的同步接口
    :param system: system prompt
    :param user:   user prompt
    :param timeout: 请求超时时间（秒）
    :return: 模型返回文本
    """
    resolved_key = (api_key or os.getenv("VOLCES_API_KEY") or VOLCES_API_KEY)
    resolved_model = (model or os.getenv("VOLCES_MODEL") or MODEL)
    resolved_endpoint = (os.getenv("VOLCES_ENDPOINT") or endpoint).strip()
    resolved_bot_id = (os.getenv("VOLCES_BOT_ID") or "").strip()

    if _is_placeholder(resolved_key) or _is_placeholder(resolved_model):
        return (
            "AI调用未配置：未检测到有效的火山方舟鉴权信息。\n"
            "请设置环境变量：\n"
            "- VOLCES_API_KEY：你的火山方舟 API Key（Bearer token）\n"
            "- VOLCES_MODEL：你的模型名称（用于 /chat/completions）\n"
            "- VOLCES_ENDPOINT：可选；模型直连建议用 https://ark.cn-beijing.volces.com/api/v3/chat/completions\n"
            "- VOLCES_BOT_ID：可选；若使用 bots 接口通常需要提供 bot_id\n"
            "配置完成后重新运行即可生成该段AI内容。"
        )

    headers = {
        "Authorization": f"Bearer {resolved_key}",
        "Content-Type": "application/json"
    }
 
    is_bots_endpoint = "/bots/" in resolved_endpoint
    # bots 接口与 model 接口的入参可能不同：优先用 bot_id，其次用 model
    if is_bots_endpoint and resolved_bot_id:
        payload = {
            "bot_id": resolved_bot_id,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user}
            ]
        }
    else:
        payload = {
            "model": resolved_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user}
            ]
        }
 
    try:
        # 避免在默认情况下泄漏 prompt；需要调试可自行打开
        if os.getenv("VOLCES_DEBUG") == "1":
            print(f"正在调用火山方舟接口: {resolved_endpoint}")
            if is_bots_endpoint and not resolved_bot_id:
                print("提示：当前使用 bots endpoint 但未设置 VOLCES_BOT_ID，将尝试按 model 直连；如仍 400，请改用 /chat/completions。")

        resp = requests.post(resolved_endpoint, json=payload, headers=headers, timeout=timeout)
        if resp.status_code == 401:
            return (
                "AI调用失败：鉴权失败(401 Unauthorized)。\n"
                "请检查 VOLCES_API_KEY 是否正确、是否有权限访问该 bot/model，或 key 是否已过期。"
            )
        if resp.status_code == 403:
            return (
                "AI调用失败：无权限(403 Forbidden)。\n"
                "请确认账号权限、bot/model 权限，以及 key 是否绑定了正确的项目/空间。"
            )
        if resp.status_code == 400:
            detail = None
            try:
                detail = resp.json()
            except Exception:
                detail = (resp.text or "").strip()
            return (
                "AI调用失败：请求参数错误(400 Bad Request)。\n"
                f"服务端返回：{detail}\n"
                "排查建议：\n"
                "- 若你传的是模型名（如 deepseek-xxx），请把 VOLCES_ENDPOINT 设为 `https://ark.cn-beijing.volces.com/api/v3/chat/completions`\n"
                "- 若你坚持用 bots 接口，请设置 VOLCES_BOT_ID 为你的 bot_id，并保持 endpoint 为 `/api/v3/bots/chat/completions`"
            )
        resp.raise_for_status()

        data = resp.json()
        content_str = data["choices"][0]["message"]["content"]
        return content_str
        # # 2. 智能清洗内容，提取纯净的JSON部分
        # json_match = re.search(r'\[[\s\S]*\]', content_str)
        # if json_match:
        #     clean_json_str = json_match.group(0)
        #     # 尝试验证一下提取出的是否是合法的JSON，防止意外
        #     try:
        #         json.loads(clean_json_str)
        #         return clean_json_str
        #     except json.JSONDecodeError:
        #         return json.dumps([{"error": "AI返回了格式错误的JSON", "details": clean_json_str}])
        # else:
        #     return json.dumps([{"error": "AI返回内容中未找到有效的JSON数组", "details": content_str}])
    except requests.RequestException as e:
        resp = getattr(e, "response", None)
        if resp is not None:
            detail = None
            try:
                detail = resp.json()
            except Exception:
                detail = (resp.text or "").strip()
            return f"AI调用失败：网络或请求异常：{e} | 详情：{detail}"
        return f"AI调用失败：网络或请求异常：{e}"
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        return f"AI调用失败：返回解析异常：{e}"
    except Exception as e:
        return f"AI调用失败：未知异常：{e}"
 
 
# 当脚本直接运行时给出一个最小示例
if __name__ == "__main__":
    print(chat_volces("""
    角色：你是专业的股市新闻筛选分析大师，根据我要求的新闻内容检索，分析后，返回我指定的严格JSON格式内容，不包含任何解释、注释或其他无关字符。
    响应示例：[{"summary": "国务院印发《新一轮千亿斤粮食产能提升行动方案》", "sentiment": "利好", "impact_score": 1.5, "sector": ["大农业"], "type": "长线", "expiry_date": "2030-12-31"}]
    强调：不要包含除了json响应示例以外任何内容
  """, """
  总结近2-3个月发布的、影响至今且未来一段时间内仍然有效的【长线】宏观或行业政策（例如XX规划、XX活动）。对每条新闻，请提供：1. 摘要(summary) 2. 情绪(sentiment: '利好'/'利空') 3. 影响权重(impact_score: 0-2分) 4. 影响的板块标签(sector: 从[{sector_themes_str}]中选择的列表) 5. 影响过期日(expiry_date: 'YYYY-MM-DD'格式)
  """))
