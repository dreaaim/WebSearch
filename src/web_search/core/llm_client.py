import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class LLMConfig:
    provider: str = "openai"
    model: str = "gpt-4o"
    api_base: str = "https://api.openai.com/v1"
    api_key: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 2048

class LLMClientBase:
    @property
    def provider_name(self) -> str:
        return "unknown"

    async def complete(self, prompt: str) -> str:
        raise NotImplementedError

    def complete_sync(self, prompt: str) -> str:
        raise NotImplementedError

    async def complete_batch(self, prompts: List[str]) -> List[str]:
        raise NotImplementedError

class MockLLMClient(LLMClientBase):
    @property
    def provider_name(self) -> str:
        return "mock"

    async def complete(self, prompt: str) -> str:
        return "mock_response"

    def complete_sync(self, prompt: str) -> str:
        return "mock_response"

    async def complete_batch(self, prompts: List[str]) -> List[str]:
        return ["mock_response" for _ in prompts]

class OpenAIClient(LLMClientBase):
    def __init__(
        self,
        model: str = "gpt-4o",
        api_base: str = "https://api.openai.com/v1",
        api_key: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        stream: bool = False,
        enable_thinking: bool = False
    ):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=api_base)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._stream = stream
        self._enable_thinking = enable_thinking

    @property
    def provider_name(self) -> str:
        return "openai"

    async def complete(self, prompt: str) -> str:
        extra_body = {}
        if self._enable_thinking:
            extra_body["enable_thinking"] = True
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            stream=self._stream,
            extra_body=extra_body if extra_body else None
        )
        if self._stream:
            content = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content += chunk.choices[0].delta.content
            return content
        return response.choices[0].message.content

    def complete_sync(self, prompt: str) -> str:
        extra_body = {}
        if self._enable_thinking:
            extra_body["enable_thinking"] = True
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            stream=False,
            extra_body=extra_body if extra_body else None
        )
        return response.choices[0].message.content

    async def complete_batch(self, prompts: List[str]) -> List[str]:
        results = []
        for prompt in prompts:
            results.append(await self.complete(prompt))
        return results

class AzureOpenAIClient(LLMClientBase):
    def __init__(
        self,
        api_base: str,
        api_key: str,
        api_version: str = "2024-06-01",
        deployment_name: str = "gpt-4o",
        temperature: float = 0.3,
        max_tokens: int = 2048
    ):
        from openai import AzureOpenAI
        self._client = AzureOpenAI(
            api_key=api_key,
            api_base=api_base,
            api_version=api_version
        )
        self._deployment = deployment_name
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def provider_name(self) -> str:
        return "azure"

    async def complete(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._temperature,
            max_tokens=self._max_tokens
        )
        return response.choices[0].message.content

    def complete_sync(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._temperature,
            max_tokens=self._max_tokens
        )
        return response.choices[0].message.content

    async def complete_batch(self, prompts: List[str]) -> List[str]:
        results = []
        for prompt in prompts:
            results.append(await self.complete(prompt))
        return results

class AnthropicClient(LLMClientBase):
    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.3,
        max_tokens: int = 2048
    ):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def complete(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def complete_sync(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    async def complete_batch(self, prompts: List[str]) -> List[str]:
        results = []
        for prompt in prompts:
            results.append(await self.complete(prompt))
        return results

class ZhipuAIClient(LLMClientBase):
    def __init__(
        self,
        api_key: str,
        model: str = "glm-4.5",
        api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature: float = 0.3,
        max_tokens: int = 2048
    ):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=api_base)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def provider_name(self) -> str:
        return "zhipuai"

    async def complete(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._temperature,
            max_tokens=self._max_tokens
        )
        return response.choices[0].message.content

    def complete_sync(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._temperature,
            max_tokens=self._max_tokens
        )
        return response.choices[0].message.content

    async def complete_batch(self, prompts: List[str]) -> List[str]:
        results = []
        for prompt in prompts:
            results.append(await self.complete(prompt))
        return results


def create_llm_client(config: Dict[str, Any]) -> LLMClientBase:
    if not config:
        return MockLLMClient()

    if config.get("azure", {}).get("enabled", False):
        azure_cfg = config["azure"]
        return AzureOpenAIClient(
            api_base=azure_cfg["api_base"],
            api_key=azure_cfg["api_key"],
            api_version=azure_cfg.get("api_version", "2024-06-01"),
            deployment_name=azure_cfg.get("deployment_name", "gpt-4o"),
            temperature=azure_cfg.get("temperature", 0.3),
            max_tokens=azure_cfg.get("max_tokens", 2048)
        )

    if config.get("anthropic", {}).get("enabled", False):
        anthropic_cfg = config["anthropic"]
        return AnthropicClient(
            api_key=anthropic_cfg["api_key"],
            model=anthropic_cfg.get("model", "claude-3-5-sonnet-20241022"),
            temperature=anthropic_cfg.get("temperature", 0.3),
            max_tokens=anthropic_cfg.get("max_tokens", 2048)
        )

    if config.get("thinking", {}).get("enabled", False):
        thinking_cfg = config["thinking"]
        api_key = thinking_cfg.get("api_key", "")
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var, "")
        return OpenAIClient(
            model=thinking_cfg.get("model", "qwen-plus"),
            api_base=thinking_cfg.get("api_base", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            api_key=api_key,
            temperature=thinking_cfg.get("temperature", 0.3),
            max_tokens=thinking_cfg.get("max_tokens", 4096),
            enable_thinking=thinking_cfg.get("enable_thinking", True)
        )

    openai_cfg = config.get("openai", {})

    api_key = openai_cfg.get("api_key")
    if api_key and api_key.startswith("${") and api_key.endswith("}"):
        env_var = api_key[2:-1]
        api_key = os.environ.get(env_var, "")

    model = openai_cfg.get("model", "gpt-4o")
    api_base = openai_cfg.get("api_base", "https://api.openai.com/v1")

    if "dashscope" in api_base:
        return OpenAIClient(
            model=model,
            api_base=api_base,
            api_key=api_key,
            temperature=openai_cfg.get("temperature", 0.3),
            max_tokens=openai_cfg.get("max_tokens", 2048),
            stream=True
        )

    if "zhipu" in model.lower():
        return ZhipuAIClient(
            api_key=api_key,
            model=model,
            api_base=api_base,
            temperature=openai_cfg.get("temperature", 0.3),
            max_tokens=openai_cfg.get("max_tokens", 2048)
        )

    return OpenAIClient(
        model=model,
        api_base=api_base,
        api_key=api_key,
        temperature=openai_cfg.get("temperature", 0.3),
        max_tokens=openai_cfg.get("max_tokens", 2048)
    )

def create_llm_clients(config: Dict[str, Any]) -> tuple:
    if not config:
        return MockLLMClient(), None

    primary = None
    thinking_client = None

    if config.get("azure", {}).get("enabled", False):
        azure_cfg = config["azure"]
        primary = AzureOpenAIClient(
            api_base=azure_cfg["api_base"],
            api_key=azure_cfg["api_key"],
            api_version=azure_cfg.get("api_version", "2024-06-01"),
            deployment_name=azure_cfg.get("deployment_name", "gpt-4o"),
            temperature=azure_cfg.get("temperature", 0.3),
            max_tokens=azure_cfg.get("max_tokens", 2048)
        )
    elif config.get("anthropic", {}).get("enabled", False):
        anthropic_cfg = config["anthropic"]
        primary = AnthropicClient(
            api_key=anthropic_cfg["api_key"],
            model=anthropic_cfg.get("model", "claude-3-5-sonnet-20241022"),
            temperature=anthropic_cfg.get("temperature", 0.3),
            max_tokens=anthropic_cfg.get("max_tokens", 2048)
        )
    else:
        openai_cfg = config.get("openai", {})
        api_key = openai_cfg.get("api_key", "")
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var, "")

        model = openai_cfg.get("model", "gpt-4o")
        api_base = openai_cfg.get("api_base", "https://api.openai.com/v1")

        if "zhipu" in model.lower():
            primary = ZhipuAIClient(
                api_key=api_key,
                model=model,
                api_base=api_base,
                temperature=openai_cfg.get("temperature", 0.3),
                max_tokens=openai_cfg.get("max_tokens", 2048)
            )
        else:
            primary = OpenAIClient(
                model=model,
                api_base=api_base,
                api_key=api_key,
                temperature=openai_cfg.get("temperature", 0.3),
                max_tokens=openai_cfg.get("max_tokens", 2048)
            )

    if config.get("thinking", {}).get("enabled", False):
        thinking_cfg = config["thinking"]
        api_key = thinking_cfg.get("api_key", "")
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var, "")
        thinking_client = OpenAIClient(
            model=thinking_cfg.get("model", "qwen-plus"),
            api_base=thinking_cfg.get("api_base", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            api_key=api_key,
            temperature=thinking_cfg.get("temperature", 0.3),
            max_tokens=thinking_cfg.get("max_tokens", 4096),
            enable_thinking=thinking_cfg.get("enable_thinking", True)
        )

    return primary, thinking_client