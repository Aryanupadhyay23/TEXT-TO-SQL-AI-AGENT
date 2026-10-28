"""JSON serialization, datetime conversions, and SSE payload chunk formatting utilities."""

import time
import json
from datetime import date, datetime, time as dt_time
from decimal import Decimal
from typing import Any, Dict


def default_json_serializer(obj: Any) -> Any:
    """Safe JSON serializer for decimals, datetimes, dates, sets, and byte objects."""
    if isinstance(obj, (datetime, date, dt_time)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return str(obj)


def format_sse_chunk(
    chunk_type: str,
    data: Any,
    conversation_id: str,
    request_id: str,
) -> Dict[str, Any]:
    """Builds a standard chunk dictionary expected by the frontend AIChatWidget."""
    ts = int(time.time() * 1000)
    payload: Dict[str, Any] = {
        "conversation_id": conversation_id,
        "request_id": request_id,
        "timestamp": ts,
        "type": chunk_type,
    }

    if chunk_type == "text":
        content_str = str(data)
        payload["data"] = {"content": content_str}
        payload["rich"] = {"type": "text", "data": {"content": content_str}}
        payload["simple"] = {"type": "text", "content": content_str}
    elif chunk_type == "sql":
        sql_str = str(data)
        payload["data"] = {"sql": sql_str}
        payload["rich"] = {"type": "sql", "data": {"sql": sql_str}}
        payload["simple"] = {"type": "sql", "content": sql_str}
    elif chunk_type == "table":
        table_rows = data if isinstance(data, list) else []
        payload["data"] = table_rows
        payload["rich"] = {"type": "table", "data": table_rows}
        payload["simple"] = {"type": "table", "data": table_rows}
    elif chunk_type == "retrieved_memory":
        payload["data"] = data
        payload["rich"] = {"type": "retrieved_memory", "data": data}
        payload["simple"] = {"type": "retrieved_memory", "data": data}
    elif chunk_type == "error":
        err_msg = str(data)
        payload["data"] = {"message": err_msg}
        payload["rich"] = {"type": "error", "data": {"message": err_msg}}
        payload["simple"] = {"type": "error", "content": err_msg}
    elif chunk_type == "status_card":
        payload["data"] = data
        if isinstance(data, dict):
            for k in ("id", "title", "status", "description", "metadata", "memories"):
                if k in data:
                    payload[k] = data[k]
        payload["rich"] = {"type": "status_card", "data": data}
        payload["simple"] = {"type": "status_card", "content": str(data)}
    else:
        payload["data"] = data
        payload["rich"] = {"type": chunk_type, "data": data}
        payload["simple"] = {"type": chunk_type, "content": str(data)}

    return payload
