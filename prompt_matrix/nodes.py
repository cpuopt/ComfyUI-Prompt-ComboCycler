from __future__ import annotations

import json
from threading import Lock
import time
from typing import Any

from .matrix import (
    MatrixSource,
    mixed_radix_indices,
    select_from_source,
    shuffle_no_repeat_index,
    source_from_text,
    stable_random_index,
)


WEB_DIRECTORY = "./web"
FIXED_RANDOM_SEED = 0


class AnyPromptMatrixSourceDict(dict):
    def __contains__(self, key: object) -> bool:
        return True

    def __getitem__(self, key: object) -> tuple[str]:
        return ("PROMPT_MATRIX_SOURCE",)


_STATE_LOCK = Lock()
_CONTROLLER_STATE: dict[str, dict[str, Any]] = {}


def _reset_controller_state(node_id: str | int | None = None) -> None:
    with _STATE_LOCK:
        if node_id is None:
            _CONTROLLER_STATE.clear()
        else:
            _CONTROLLER_STATE.pop(str(node_id), None)


def _natural_source_key(name: str) -> tuple[str, int, str]:
    prefix, _, suffix = name.rpartition("_")
    if suffix.isdigit():
        return (prefix, int(suffix), name)
    return (name, 0, name)


def _source_payload_signature(sources: list[MatrixSource], traversal: str, join_separator: str) -> str:
    return json.dumps(
        {
            "sources": [source.to_payload() for source in sources],
            "traversal": traversal,
            "join_separator": join_separator,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _extract_sources(kwargs: dict[str, Any]) -> list[MatrixSource]:
    sources: list[MatrixSource] = []
    for key in sorted(kwargs.keys(), key=_natural_source_key):
        value = kwargs[key]
        if isinstance(value, MatrixSource):
            sources.append(value)
        elif isinstance(value, dict) and value.get("_prompt_matrix_source"):
            sources.append(MatrixSource.from_payload(value))
    return sources


class PromptMatrixSource:
    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": "masterpiece\nbest quality"}),
                "mode": (["combination", "permutation"], {"default": "combination"}),
                "choose_k": ("INT", {"default": 1, "min": 1, "max": 9999, "step": 1}),
                "item_separator": ("STRING", {"default": ", "}),
                "enabled": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "text_input": ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("PROMPT_MATRIX_SOURCE", "INT")
    RETURN_NAMES = ("source", "count")
    FUNCTION = "build"
    CATEGORY = "prompt/matrix"

    def build(
        self,
        text: str,
        mode: str,
        choose_k: int,
        item_separator: str,
        enabled: bool,
        text_input: str | None = None,
    ) -> dict:
        source_text = text_input if text_input is not None else text
        source = source_from_text(source_text, mode, choose_k, item_separator, enabled)
        status = f"{source.count} possible"
        return {
            "ui": {"status": [status]},
            "result": (source.to_payload(), source.count),
        }


class PromptMatrixController:
    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "traversal": (["random_with_repeat", "sequential", "shuffle_no_repeat"], {"default": "random_with_repeat"}),
                "join_separator": ("STRING", {"default": ", "}),
            },
            "optional": AnyPromptMatrixSourceDict(),
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("STRING", "INT", "INT")
    RETURN_NAMES = ("prompt", "index", "total")
    FUNCTION = "compose"
    CATEGORY = "prompt/matrix"

    @classmethod
    def VALIDATE_INPUTS(cls, input_types: dict | None = None, **kwargs: Any) -> bool:
        return True

    @classmethod
    def IS_CHANGED(cls, **kwargs: Any) -> int:
        return time.time_ns()

    def compose(self, traversal: str, join_separator: str, unique_id: str | None = None, **kwargs: Any) -> dict:
        sources = _extract_sources(kwargs)
        counts = [source.count for source in sources if source.enabled]
        total = 1
        for count in counts:
            total *= max(1, int(count))

        node_key = str(unique_id or "__default__")
        signature = _source_payload_signature(sources, traversal, join_separator)
        seed = FIXED_RANDOM_SEED

        with _STATE_LOCK:
            state = _CONTROLLER_STATE.setdefault(node_key, {"cursor": 0, "signature": signature})
            if state.get("signature") != signature:
                state["cursor"] = 0
                state["signature"] = signature

            cursor = int(state.get("cursor", 0))
            if traversal == "sequential":
                global_index = cursor % total
            elif traversal == "shuffle_no_repeat":
                global_index = shuffle_no_repeat_index(total, seed, cursor)
            else:
                global_index = stable_random_index(total, seed, cursor)

            state["cursor"] = cursor + 1

        local_indices = mixed_radix_indices(global_index, [source.count for source in sources])
        parts = []
        for source, local_index in zip(sources, local_indices):
            part = select_from_source(source, local_index)
            if part:
                parts.append(part)

        prompt = str(join_separator).join(parts)
        status = f"{global_index + 1} / {total}"
        return {
            "ui": {"status": [status], "prompt": [prompt]},
            "result": (prompt, global_index + 1, total),
        }


NODE_CLASS_MAPPINGS = {
    "PromptMatrixSource": PromptMatrixSource,
    "PromptMatrixController": PromptMatrixController,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptMatrixSource": "Prompt Matrix Source",
    "PromptMatrixController": "Prompt Matrix Controller",
}


try:
    from aiohttp import web
    from server import PromptServer

    @PromptServer.instance.routes.post("/prompt_matrix/reset_cursor")
    async def reset_cursor(request):
        payload = await request.json()
        _reset_controller_state(payload.get("node_id"))
        return web.json_response({"ok": True})

    @PromptServer.instance.routes.get("/prompt_matrix/status")
    async def matrix_status(request):
        node_id = request.query.get("node_id")
        with _STATE_LOCK:
            if node_id is None:
                status = {key: dict(value) for key, value in _CONTROLLER_STATE.items()}
            else:
                status = dict(_CONTROLLER_STATE.get(str(node_id), {}))
        return web.json_response({"ok": True, "status": status})
except Exception:
    pass
