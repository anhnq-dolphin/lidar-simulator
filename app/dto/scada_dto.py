from typing import Any, Literal

from pydantic import BaseModel, Field

DEFAULT_OPC_ENDPOINT = "opc.tcp://192.168.0.43:4840"

DEFAULT_SHIP_NODES = [
    "ns=2;s=Ships/Ship_01/Distance",
    "ns=2;s=Ships/Ship_01/Speed",
    "ns=2;s=Ships/Ship_01/WarningLevel",
    "ns=2;s=Ships/Ship_01/Length",
    "ns=2;s=Ships/Ship_01/Width",
    "ns=2;s=Ships/Ship_01/Height",
]

DEFAULT_INFRASTRUCTURE_NODES = [
    "ns=2;s=Infrastructure/WaterLevelUpstream",
    "ns=2;s=Infrastructure/WaterLevelDownstream",
    "ns=2;s=Infrastructure/GateLock",
    "ns=2;s=Infrastructure/SluiceGate",
]

OpcUaValueType = Literal["auto", "string", "double", "int", "bool"]


class ScadaDefaultNodesResponse(BaseModel):
    endpoint_url: str = DEFAULT_OPC_ENDPOINT
    read_nodes: list[str] = Field(default_factory=lambda: list(DEFAULT_SHIP_NODES))
    write_nodes: list[str] = Field(default_factory=lambda: list(DEFAULT_INFRASTRUCTURE_NODES))


class ScadaReadRequest(BaseModel):
    endpoint_url: str = DEFAULT_OPC_ENDPOINT
    node_ids: list[str] = Field(default_factory=lambda: list(DEFAULT_SHIP_NODES), min_length=1)


class ScadaReadResponse(BaseModel):
    endpoint_url: str
    values: dict[str, Any]


class ScadaBrowseRequest(BaseModel):
    endpoint_url: str = DEFAULT_OPC_ENDPOINT
    node_id: str | None = Field(default=None, examples=["ns=2;s=Ships"])
    recursive: bool = False


class ScadaBrowseResponse(BaseModel):
    endpoint_url: str
    node_id: str | None
    children: list[dict]


class ScadaWriteItem(BaseModel):
    node_id: str
    value: Any
    value_type: OpcUaValueType = "auto"


class ScadaWriteRequest(BaseModel):
    endpoint_url: str = DEFAULT_OPC_ENDPOINT
    nodes: list[ScadaWriteItem] = Field(..., min_length=1)


class ScadaWriteResponse(BaseModel):
    endpoint_url: str
    results: dict[str, Any]
