"""(Real Time) KPI Calculation Engine."""

import json
from datetime import datetime

import requests
import numpy as np
import numexpr as ne

from aiokafka import AIOKafkaConsumer
from fastapi import WebSocket

from app.models.real_time_kpi import RealTimeKPI
from app.models.requests.gui import RealTimeKPIRequest
from app.models.responses.gui import RealTimeKPIResponse
from app.utils.kafka_admin import delete_kafka_topic


class KPIEngine:
    """
    This class represents the core engine for real-time KPI computation. It integrates Kafka for message consumption,
    numpy and numexpr for numerical computation, and WebSocket for real-time
    communication with a GUI.

    :param topic: The Kafka topic from which the engine consumes data.
    :type topic: str
    :param port: The port number for the Kafka server.
    :type port: str
    :param servers: The address of the Kafka server.
    :type servers: str
    :param evaluable_formula_info: A dictionary containing the formula,
        operations, and aggregation rules for KPI computation.
    :type evaluable_formula_info: dict
    """

    instance = None

    def __init__(self, topic, port, servers, evaluable_formula_info) -> None:
        """
        Constructor method for initializing the KPIEngine.

        :param topic: The Kafka topic to consume messages from.
        :type topic: str
        :param port: The Kafka broker port.
        :type port: str
        :param servers: The Kafka broker server address.
        :type servers: str
        :param evaluable_formula_info: Dictionary containing formula information.
        :type evaluable_formula_info: dict
        """
        self._topic = topic
        self._port = port
        self._servers = servers
        self.consumer = self.create_consumer()
        self.partial_result = {}
        self.evaluable_formula_info = evaluable_formula_info
        KPIEngine.instance = self
        print(
            "KPI Engine initialized: created consumer. Topic: ",
            topic,
            " Port: ",
            port,
            " Servers: ",
            servers,
        )

    def create_consumer(self):
        """
        Creates and returns an AIOKafkaConsumer instance for consuming messages from the Kafka topic.

        This method sets up the Kafka consumer with the necessary configurations and
        decodes the messages into `RealTimeKPI` objects.

        :return: A Kafka consumer instance configured for the specified topic.
        :rtype: AIOKafkaConsumer
        """

        def decode_message(message: bytes):
            """
            Decodes the message from Kafka into a list of `RealTimeKPI` objects.

            :param message: The message received from Kafka.
            :type message: bytes
            :return: A list of `RealTimeKPI` objects.
            """
            return [
                RealTimeKPI.from_json(json.loads(item))
                for item in json.loads(message.decode("utf-8"))
            ]

        return AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=f"{self._servers}:{self._port}",
            value_deserializer=decode_message,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )

    async def start_consumer(self):
        """
        Starts the Kafka consumer. Ensures that the consumer is correctly initialized and begins listening
        for messages on the assigned topic.

        :raises Exception: If the consumer fails to start.
        :return: Dictionary indicating success or failure.
        :rtype: dict
        """
        try:
            await self.consumer.start()
        except Exception as e:
            print(f"Error starting consumer: {e}")
            return {"Error": f"Error starting consumer: {str(e)}"}

    async def consume(
        self, websocket: WebSocket, request: RealTimeKPIRequest, stop_event
    ):
        """
        Continuously consumes messages from the Kafka topic, processes the data to compute KPIs,
        and sends the results to the GUI via WebSocket.

        :param websocket: The websocket server on which to send data to the GUI
        :type websocket: WebSocket
        :param request: The request containing user-defined parameters for KPI computation.
        :type request: RealTimeKPIRequest
        :param stop_event: An event to signal the termination of consumption.
        :type stop_event: threading.Event
        """
        try:
            print("Consuming messages...")
            while not stop_event.is_set():
                # get the last message from the topic
                real_time_kpis = (await self.consumer.getone()).value

                # compute real time kpis
                response = self.compute_real_time(real_time_kpis, request)

                # send the computed result to the GUI via websocket
                await websocket.send_json(response.to_json())

        except Exception as e:
            print("Error in consumer: ", e)
        finally:
            await self.consumer.stop()

    def compute_real_time(
        self, real_time_kpis: list[RealTimeKPI], request: RealTimeKPIRequest
    ) -> RealTimeKPIResponse:
        """
        Processes a RealTimeKPIRequest and computes the real-time KPIs based on the provided data.
        This method converts the RealTimeKPIs to numpy arrays, appends them to the already seen KPIs (in the streaming)
        state variable, evaluates the formula with numexpr, handling time and machine-operation aggregations,
        and finally returns a RealTimeKPIResponse object.

        :param real_time_kpis: List of real-time KPI data objects.
        :type real_time_kpis: list[RealTimeKPI]
        :param request: Request object defining computation parameters.
        :type request: RealTimeKPIRequest
        :return: Computed KPI results encapsulated in a response object.
        :rtype: RealTimeKPIResponse
        """

        special = bool(self.evaluable_formula_info["particular"])
        # Convert real_time_kpis to numpy arrays
        for kpi in real_time_kpis:
            complete_name = f"{kpi.kpi}_{kpi.column}"
            if special:
                complete_name += f"_{kpi.operation}"
            if complete_name not in self.partial_result:
                self.partial_result[complete_name] = np.empty((0, len(kpi.values)))
            self.partial_result[complete_name] = np.vstack(
                [self.partial_result[complete_name], kpi.values]
            )

        # Set globals for involved KPIs
        involved_kpis = self.partial_result.keys()
        for base_kpi in involved_kpis:
            if not special:
                globals()[base_kpi] = self.partial_result[base_kpi]
            else:
                # if it is particular we made the aggregation inside and not outside
                aggregation = self.evaluable_formula_info["agg"]
                globals()[base_kpi] = getattr(np, aggregation)(
                    self.partial_result[base_kpi], axis=1
                )

        # Evaluate the formula
        formula = self.evaluable_formula_info["formula"]
        results = ne.evaluate(formula)

        # Aggregate the result
        out = results
        # we check if it is particular, so we make the final aggregation
        if not special:
            aggregation = self.evaluable_formula_info["agg"]
            out = getattr(np, aggregation)(results, axis=1)

        time_aggregation = request.time_aggregation
        value = getattr(np, time_aggregation)(out)

        response = RealTimeKPIResponse(label=str(datetime.now()), value=value)

        return response

    async def stop(self):
        """
        Stops the Kafka consumer, cleans up WebSocket connections, and sends a termination signal
        to the data preprocessing service.
        This method notifies the data preprocessing service to stop sending data to the Kafka topic, stopping the
        AIOKafkaProducer.

        :raises Exception: If there is an error during the shutdown process.
        """
        try:
            if self.consumer:
                await self.consumer.stop()

            response = requests.get(
                "http://data-preprocessing-container:8003/real-time/stop",
            )
            response.raise_for_status()

            await delete_kafka_topic(self._topic, f"{self._servers}:{self._port}")

        except Exception as e:
            print(f"Error stopping connections: {e}")
