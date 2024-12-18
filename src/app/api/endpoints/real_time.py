""" Real-time KPI computation endpoint."""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from threading import Event
import os

from app.kpi_engine.kpi_engine import KPIEngine
from app.kpi_engine.regexp import prepare_for_real_time
from app.models.requests.data_processing import KPIStreamingRequest
from app.models.requests.gui import RealTimeKPIRequest
from app.models.responses.gui import RealTimeResponse
from app.services.data_processing import connect_to_publisher
from app.utils.kafka_admin import delete_kafka_topic

router = APIRouter()

stop_event = Event()
consumer_task = None
kpi_engine = None

KAFKA_TOPIC_NAME = os.getenv("KAFKA_TOPIC_NAME")
KAFKA_SERVER = os.getenv("KAFKA_SERVER")
KAFKA_PORT = os.getenv("KAFKA_PORT")


@router.websocket("/")
async def real_time_session(websocket: WebSocket) -> RealTimeResponse:
    """
    Manages a real-time KPI WebSocket session.

    This function handles incoming WebSocket connections, allowing the client to start or stop
    a real-time KPI session. It validates incoming messages and processes requests to either
    initialize a session or terminate it. Invalid messages will result in the WebSocket connection
    being closed. The session is managed by the `handle_real_time_session` function.

    :param websocket: The WebSocket connection for client-server communication.
    :type websocket: WebSocket
    :return: A response indicating the result of the WebSocket operation (informative).
    :rtype: RealTimeResponse
    """
    await websocket.accept()
    try:
        while True:

            data = await websocket.receive_json()
            if data == {"message": "stop"}:
                await stop_consumer()
                await websocket.close()
                break
            elif data["message"] == "start":
                print("Starting real-time session, data:", data)
                request = RealTimeKPIRequest(**data["request"])
                _ = await handle_real_time_session(websocket, request)
            else:
                response = RealTimeResponse(
                    message="Invalid message received in the websocket", status=400
                )
                await websocket.send_json(response.dict())
                await websocket.close()
                break
    except WebSocketDisconnect:
        await stop_consumer()
        await websocket.close()


async def handle_real_time_session(
    websocket: WebSocket, request: RealTimeKPIRequest
) -> RealTimeResponse:
    """
    Initiates and manages a real-time KPI session.

    This function validates the incoming request, prepares the necessary configurations for
    KPI computation, and starts the AIOKafkaConsumer to process real-time data. The consumer is started asynchronously
    in a separate task, allowing the WebSocket connection to remain open for real-time communication and the other
    endpoints to be called concurrently. The session can be stopped by sending a "stop" message through the WebSocket.

    :param websocket: The WebSocket connection used for real-time communication.
    :type websocket: WebSocket
    :param request: Details of the KPI request including KPI name, machines, operations, and other parameters.
    :type request: RealTimeKPIRequest
    :return: A response indicating the success or failure of the session initiation.
    :rtype: RealTimeResponse
    """
    global consumer_task, stop_event, kpi_engine

    if consumer_task and not consumer_task.done():
        return RealTimeResponse(
            message="A real-time session is already running.", status=400
        )

    stop_event.clear()

    involved_kpis, evaluable_formula_info = prepare_for_real_time(request.name)

    special = bool(evaluable_formula_info["particular"])
    if special:
        request.operations = list(evaluable_formula_info["operations_f"].values())

    kpi_streaming_request = KPIStreamingRequest(
        kpis=involved_kpis,
        machines=request.machines,
        operations=request.operations,
        special=special,
    )
    kpi_engine = KPIEngine(
        KAFKA_TOPIC_NAME, KAFKA_PORT, KAFKA_SERVER, evaluable_formula_info
    )

    data_preprocessing_response = connect_to_publisher(kpi_streaming_request)
    print(
        "Data Preprocessing Response on connection trial:", data_preprocessing_response
    )

    try:
        # Start the consumer and wait until it's ready
        await kpi_engine.consumer.start()
        print("Consumer started successfully")
    except Exception as e:
        print(f"Error starting consumer: {e}")
        return RealTimeResponse(
            message=f"Error starting consumer: {str(e)}", status=500
        )

    consumer_task = asyncio.create_task(
        kpi_engine.consume(websocket, request, stop_event)
    )

    return RealTimeResponse(message="Real-time session started", status=200)


async def stop_consumer() -> RealTimeResponse:
    """
    Stops the currently running Kafka consumer.

    This endpoint stops the real-time KPI session by signaling the Kafka consumer (in the :class:`KPIEngine
    <src.app.kpi_engine.kpi_engine.KPIEngine>` to terminate, processing any remaining data, and closing all active
    connections.

    :return: A response indicating the success or failure of stopping the consumer.
    :rtype: RealTimeResponse
    """

    global stop_event, consumer_task

    if consumer_task is None or kpi_engine is None:
        return RealTimeResponse(message="The consumer has not started yet.", status=400)

    if consumer_task.done():
        return RealTimeResponse(message="The consumer has already stopped.", status=400)

    stop_event.set()  # Signal the task to stop

    # Process the last element of the consumer
    await consumer_task

    # Close all connections
    await kpi_engine.stop()

    return RealTimeResponse(
        message="Real-time session successfully stopped", status=200
    )


async def shutdown_event():
    """
    Handles application shutdown by stopping the Kafka consumer and cleaning up resources.

    This function is triggered during application shutdown. It stops the Kafka consumer
    and deletes the Kafka topic associated with the real-time session.

    :raises Exception: If errors occur during the cleanup process.
    """
    global stop_event
    stop_event.set()  # Signal the task to stop
    if consumer_task and not consumer_task.done():
        await consumer_task  # Wait for the task to finish
    await delete_kafka_topic(KAFKA_TOPIC_NAME, f"{KAFKA_SERVER}:{KAFKA_PORT}")
