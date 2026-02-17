from fastapi import FastAPI
from src.routers import event_route as api
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
app.include_router(api.router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "X-Requested-With",
    ],
)