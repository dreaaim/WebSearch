import yaml
import os
from typing import Dict, Any, List
from dataclasses import dataclass, field
from .schemas import ProviderConfig, PriorityRulesConfig, KOLThresholds

@dataclass
class Settings:
    whitelist: List[Any] = field(default_factory=list)
    blacklist: List[Any] = field(default_factory=list)
    priority_rules: Dict[str, Any] = field(default_factory=dict)
    providers: Dict[str, Any] = field(default_factory=dict)
    llm: Dict[str, Any] = field(default_factory=dict)
    embedding: Dict[str, Any] = field(default_factory=dict)
    reranker: Dict[str, Any] = field(default_factory=dict)
    rewriter: Dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> Dict[str, Any]:
        return {
            "whitelist": self.whitelist,
            "blacklist": self.blacklist,
            "priority_rules": self.priority_rules,
            "providers": self.providers,
            "llm": self.llm,
            "embedding": self.embedding,
            "reranker": self.reranker,
            "rewriter": self.rewriter,
        }

def load_yaml(file_path: str) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        return {}
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

def load_config(config_dir: str = "configs") -> Dict[str, Any]:
    config = {}

    whitelist_path = os.path.join(config_dir, "whitelist.yaml")
    if os.path.exists(whitelist_path):
        config["whitelist"] = load_yaml(whitelist_path).get("whitelist", [])

    blacklist_path = os.path.join(config_dir, "blacklist.yaml")
    if os.path.exists(blacklist_path):
        config["blacklist"] = load_yaml(blacklist_path).get("blacklist", [])

    priority_path = os.path.join(config_dir, "priority_rules.yaml")
    if os.path.exists(priority_path):
        config["priority_rules"] = load_yaml(priority_path)

    providers_path = os.path.join(config_dir, "providers.yaml")
    if os.path.exists(providers_path):
        config["providers"] = load_yaml(providers_path).get("providers", {})

    llm_path = os.path.join(config_dir, "llm.yaml")
    if os.path.exists(llm_path):
        config["llm"] = load_yaml(llm_path).get("llm", {})

    embedding_path = os.path.join(config_dir, "embedding.yaml")
    if os.path.exists(embedding_path):
        config["embedding"] = load_yaml(embedding_path).get("embedding", {})

    reranker_path = os.path.join(config_dir, "reranker.yaml")
    if os.path.exists(reranker_path):
        config["reranker"] = load_yaml(reranker_path).get("reranker", {})

    rewriter_path = os.path.join(config_dir, "rewriter.yaml")
    if os.path.exists(rewriter_path):
        config["rewriter"] = load_yaml(rewriter_path).get("query_rewriter", {})

    return config

def get_provider_config(config: Dict[str, Any], provider_name: str) -> ProviderConfig:
    providers = config.get("providers", {})
    provider_data = providers.get(provider_name, {})
    return ProviderConfig(
        enabled=provider_data.get("enabled", False),
        base_url=provider_data.get("base_url"),
        api_key=provider_data.get("api_key"),
        default_engines=provider_data.get("default_engines"),
        timeout=provider_data.get("timeout", 30),
        retry=provider_data.get("retry", 3),
        max_results=provider_data.get("max_results", 10),
        include_answer=provider_data.get("include_answer", True),
        text=provider_data.get("text", True)
    )
