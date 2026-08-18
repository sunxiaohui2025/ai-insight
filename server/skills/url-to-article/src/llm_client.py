"""Kimi LLM 客户端"""
import requests
import json
from typing import List, Dict
from src.config import Config


class LLMClient:
    def __init__(self):
        self.api_base = Config.KIMI_API_BASE
        self.model = Config.KIMI_MODEL
        self.api_key = Config.KIMI_API_KEY
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = None
    ) -> str:
        """
        调用 Kimi API

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 输出 token 上限，默认取 Config.MAX_OUTPUT_TOKENS

        Returns:
            str: 模型返回的内容
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            # 显式指定输出上限，否则服务端默认值会把长 HTML 截断
            "max_tokens": max_tokens or Config.MAX_OUTPUT_TOKENS
        }

        try:
            response = requests.post(
                self.api_base,
                headers=headers,
                json=payload,
                timeout=Config.LLM_TIMEOUT
            )
            response.raise_for_status()

            result = response.json()
            choice = result["choices"][0]

            # 输出被截断时给出明确提示，便于定位内容不全的问题
            finish_reason = choice.get("finish_reason")
            if finish_reason == "length":
                usage = result.get("usage") or {}
                print(
                    f"⚠ 模型输出达到长度上限被截断"
                    f"（completion_tokens={usage.get('completion_tokens')}，"
                    f"上限={payload['max_tokens']}）"
                )

            return choice["message"]["content"]

        except Exception as e:
            print(f"LLM API 调用失败: {e}")
            raise

    def chat_simple(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = None
    ) -> str:
        """简化的单轮对话接口"""
        if len(prompt) > Config.MAX_INPUT_CHARS:
            print(
                f"⚠ 输入长度 {len(prompt)} 字符超过兜底上限 "
                f"{Config.MAX_INPUT_CHARS}，将截断尾部"
            )
            prompt = prompt[:Config.MAX_INPUT_CHARS]

        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, temperature, max_tokens)
