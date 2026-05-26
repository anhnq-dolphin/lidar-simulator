from fastapi import FastAPI
from app.router import register_routers

app = FastAPI()
register_routers(app)
