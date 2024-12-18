# app/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.api.router import api_router
from app.api.endpoints.real_time import shutdown_event

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


def start():
    """
    Starts the FastAPI application using Uvicorn.

    This function initializes and runs the FastAPI application with Uvicorn server.
    The host is determined based on the environment variable `RUNNING_IN_DOCKER`.
    If running inside Docker, the host is set to '0.0.0.0', otherwise, it defaults to '127.0.0.1'.

    :raises RuntimeError: If the server fails to start.
    """

    host = "127.0.0.1"
    if os.getenv("RUNNING_IN_DOCKER"):
        host = "0.0.0.0"
    uvicorn.run("src.app.main:app", host=host, port=8008, reload=True)


@app.on_event("shutdown")
async def shutdown():
    """
    Shuts down the application gracefully.

    This function is called when the application is about to shut down.
    It ensures that any necessary cleanup or shutdown processes are executed.

    """
    await shutdown_event()


@app.get("/")
def read_root():
    """
    Handles the root GET endpoint.
    This endpoint returns a welcome message to confirm that the service is running.

    :return: A welcome message.
    :rtype: dict
    """

    return {"Message": "Welcome to the KPI Engine!"}


@app.get("/health/")
def health_check():
    """
    Health check GET endpoint.

    This endpoint is used to check if the service is running and responding correctly.

    :return: A dictionary indicating the health status of the service.
    :rtype: dict
    """
    return {"Status": "ok"}
