import time
import json
import logging
from typing import Any, Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class DebugStage(Enum):
    QUERY_REWRITE = "query_rewrite"
    SEARCH = "search"
    SOURCE_CLASSIFY = "source_classify"
    EMBEDDING = "embedding"
    COLLISION_DETECT = "collision_detect"
    RERANK = "rerank"
    SUMMARY = "summary"


class DebugLevel(Enum):
    BASIC = "basic"
    VERBOSE = "verbose"
    PERFORMANCE = "performance"


class DebugOutput(Enum):
    LOG = "log"
    STDOUT = "stdout"
    BOTH = "both"


class DebugLogger:
    def __init__(
        self,
        enabled: bool = False,
        level: str = "basic",
        output: str = "log"
    ):
        self.enabled = enabled
        self.level = DebugLevel(level) if isinstance(level, str) else level
        self.output = DebugOutput(output) if isinstance(output, str) else output
        self._timing_stack: Dict[str, Dict[str, Any]] = {}
        self._stage_data: Dict[str, Dict[str, Any]] = {}

    def log_stage_start(self, stage: str, data: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        self._timing_stack[stage] = {"start": time.time(), "data": data}
        self._emit(stage, {"event": "stage_start", "input": self._sanitize(data)}, level=DebugLevel.VERBOSE)

    def log_stage_end(self, stage: str, output: Dict[str, Any]) -> float:
        if not self.enabled:
            return 0.0
        if stage not in self._timing_stack:
            return 0.0
        start_time = self._timing_stack[stage]["start"]
        input_data = self._timing_stack[stage]["data"]
        duration_ms = (time.time() - start_time) * 1000
        stage_info = {
            "event": "stage_end",
            "input": self._sanitize(input_data),
            "output": self._sanitize(output),
            "duration_ms": round(duration_ms, 2)
        }
        self._stage_data[stage] = stage_info
        self._emit(stage, stage_info)
        del self._timing_stack[stage]
        return duration_ms

    def log_object(self, stage: str, obj_name: str, obj: Any) -> None:
        if not self.enabled:
            return
        if self.level != DebugLevel.VERBOSE:
            return
        obj_data = self._serialize_object(obj)
        self._emit(f"{stage}.{obj_name}", {"event": "object", "data": obj_data}, level=DebugLevel.VERBOSE)

    def log_performance_summary(self, total_duration_ms: float) -> None:
        if not self.enabled:
            return
        stage_durations = {
            stage: info["duration_ms"]
            for stage, info in self._stage_data.items()
        }
        bottleneck_stage = max(stage_durations, key=stage_durations.get) if stage_durations else None
        summary = {
            "event": "performance_summary",
            "total_duration_ms": round(total_duration_ms, 2),
            "stage_durations": {k: round(v, 2) for k, v in stage_durations.items()},
            "bottleneck_stage": bottleneck_stage
        }
        self._emit("performance", summary)

    def get_stage_data(self) -> Dict[str, Dict[str, Any]]:
        return self._stage_data.copy()

    def get_all_debug_info(self) -> Dict[str, Any]:
        return {
            "stages": self._stage_data,
            "config": {
                "enabled": self.enabled,
                "level": self.level.value if isinstance(self.level, DebugLevel) else self.level,
                "output": self.output.value if isinstance(self.output, DebugOutput) else self.output
            }
        }

    def _emit(self, stage: str, data: Dict[str, Any], level: DebugLevel = None) -> None:
        if level is None:
            level = self.level
        if isinstance(level, str):
            level = DebugLevel(level)
        if isinstance(self.level, str):
            self_level = DebugLevel(self.level)
        else:
            self_level = self.level
        if level == DebugLevel.BASIC and self_level == DebugLevel.VERBOSE:
            return
        json_data = json.dumps(
            {"stage": stage, **data},
            ensure_ascii=False,
            default=str,
            indent=None,
            separators=(',', ':')
        )
        if self.output in [DebugOutput.LOG, "log"]:
            logger.debug(json_data)
        if self.output in [DebugOutput.STDOUT, "stdout", "both"]:
            print(json_data)

    def _sanitize(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: self._sanitize(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize(item) for item in data]
        elif hasattr(data, '__dict__'):
            return self._sanitize(data.__dict__)
        elif hasattr(data, 'to_dict') and callable(data.to_dict):
            return self._sanitize(data.to_dict())
        else:
            return data

    def _serialize_object(self, obj: Any) -> Any:
        if hasattr(obj, 'to_dict') and callable(obj.to_dict):
            return obj.to_dict()
        elif hasattr(obj, '__dict__'):
            return self._sanitize(obj.__dict__)
        else:
            return obj


def to_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if hasattr(obj, 'to_dict') and callable(obj.to_dict):
        return obj.to_dict()
    elif hasattr(obj, '__dict__'):
        return {k: to_dict(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_dict(item) for item in obj]
    else:
        return obj


def create_debug_logger(
    debug: bool = False,
    debug_level: str = "basic",
    debug_output: str = "stdout"
) -> DebugLogger:
    env_debug = env_get_bool("WEB_SEARCH_DEBUG", False)
    enabled = debug or env_debug
    env_level = env_get_str("WEB_SEARCH_DEBUG_LEVEL", debug_level)
    env_output = env_get_str("WEB_SEARCH_DEBUG_OUTPUT", debug_output)
    return DebugLogger(enabled=enabled, level=env_level, output=env_output)


def env_get_bool(key: str, default: bool) -> bool:
    import os
    val = os.environ.get(key, "").lower()
    if val in ["1", "true", "yes", "on"]:
        return True
    if val in ["0", "false", "no", "off"]:
        return False
    return default


def env_get_str(key: str, default: str) -> str:
    import os
    return os.environ.get(key, default)
