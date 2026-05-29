from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.dto.scada_dto import OpcUaValueType, ScadaReadRequest, ScadaWriteRequest


def _load_client_class():
    try:
        from asyncua import Client
    except ImportError as exc:
        raise RuntimeError("missing dependency asyncua; install with: .venv/bin/python -m pip install asyncua") from exc
    return Client


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)


def _coerce_value(value: Any, value_type: OpcUaValueType) -> Any:
    if value_type == "auto":
        return value
    if value_type == "string":
        return str(value)
    if value_type == "double":
        return float(value)
    if value_type == "int":
        return int(value)
    if value_type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
        return bool(value)
    return value


class OpcUaScadaService:
    async def browse(self, endpoint_url: str, node_id: str | None = None, recursive: bool = False) -> list[dict]:
        Client = _load_client_class()
        async with Client(endpoint_url) as client:
            root = client.get_node(node_id) if node_id else client.nodes.objects
            return await self._browse_node(root, recursive, depth=0)

    async def _browse_node(self, node, recursive: bool, depth: int) -> list[dict]:
        if depth > 6:
            return []
        results = []
        try:
            children = await node.get_children()
        except Exception:
            return []
        for child in children:
            try:
                browse_name = await child.read_browse_name()
                node_class = await child.read_node_class()
                entry = {
                    "node_id": child.nodeid.to_string(),
                    "name": browse_name.Name,
                    "node_class": str(node_class),
                }
                if recursive:
                    entry["children"] = await self._browse_node(child, recursive=True, depth=depth + 1)
                results.append(entry)
            except Exception:
                continue
        return results

    async def read_nodes(self, req: ScadaReadRequest) -> dict[str, Any]:
        Client = _load_client_class()
        values: dict[str, Any] = {}
        async with Client(req.endpoint_url) as client:
            for node_id in req.node_ids:
                node = client.get_node(node_id)
                values[node_id] = _json_safe(await node.read_value())
        return values

    async def write_nodes(self, req: ScadaWriteRequest) -> dict[str, Any]:
        Client = _load_client_class()
        from asyncua import ua
        results: dict[str, Any] = {}
        async with Client(req.endpoint_url) as client:
            for item in req.nodes:
                node = client.get_node(item.node_id)
                existing = await node.read_data_value()
                variant_type = existing.Value.VariantType
                value = _coerce_value(item.value, item.value_type)
                await node.write_value(ua.DataValue(ua.Variant(value, variant_type)))
                results[item.node_id] = _json_safe(value)
        return results
