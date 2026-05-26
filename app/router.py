from fastapi import FastAPI
from app.handler.user_handler import router as user_router
from app.handler.sim_lidar_handler import router as sim_lidar_router
from app.handler.websocket_handler import router as websocket_router


def register_routers(app: FastAPI) -> None:
    app.include_router(user_router)
    app.include_router(sim_lidar_router)
    app.include_router(websocket_router)
