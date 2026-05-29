from fastapi import APIRouter, HTTPException

from app.dto.scada_dto import (
    ScadaBrowseRequest,
    ScadaBrowseResponse,
    ScadaDefaultNodesResponse,
    ScadaReadRequest,
    ScadaReadResponse,
    ScadaWriteRequest,
    ScadaWriteResponse,
)
from app.service.opcua_scada_service import OpcUaScadaService

router = APIRouter(prefix="/api/v1/scada", tags=["scada-client"])
service = OpcUaScadaService()


@router.get("/nodes", response_model=ScadaDefaultNodesResponse)
def default_nodes():
    return ScadaDefaultNodesResponse()


@router.post("/browse", response_model=ScadaBrowseResponse)
async def browse_nodes(req: ScadaBrowseRequest):
    try:
        children = await service.browse(req.endpoint_url, req.node_id, req.recursive)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"opc ua browse failed: {exc}")
    return ScadaBrowseResponse(endpoint_url=req.endpoint_url, node_id=req.node_id, children=children)


@router.post("/read", response_model=ScadaReadResponse)
async def read_nodes(req: ScadaReadRequest):
    try:
        values = await service.read_nodes(req)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"opc ua read failed: {exc}")
    return ScadaReadResponse(endpoint_url=req.endpoint_url, values=values)


@router.post("/write", response_model=ScadaWriteResponse)
async def write_node(req: ScadaWriteRequest):
    try:
        results = await service.write_nodes(req)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"opc ua write failed: {exc}")
    return ScadaWriteResponse(endpoint_url=req.endpoint_url, results=results)
