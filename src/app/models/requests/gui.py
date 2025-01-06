from datetime import datetime
from pydantic import BaseModel


class RealTimeKPIRequest:
    """
    Represents a request for real-time KPI data with specific machines, operations, and aggregation details.
    This request is sent by the GUI via the websocket protocol to provide information about the KPIs to be computed.

    :param name: The name of the KPI to be requested.
    :type name: str
    :param machines: A list of machines for which the KPI data is requested.
    :type machines: list
    :param operations: A list of operations related to the KPI request.
    :type operations: list
    :param time_aggregation: The time aggregation method
    :type time_aggregation: str
    :param start_date: The start date and time for the KPI data request (YYYY-MM-DD HH:MM:SS).
    :type start_date: datetime
    """

    name: str
    machines: list
    operations: list
    time_aggregation: str
    start_date: datetime  # (YYYY-MM-DD HH:MM:SS)

    def __init__(self, name, machines, operations, time_aggregation, start_date):
        """
        Constructor method for initializing the RealTimeKPIRequest.

        :param name: The name of the KPI to be requested.
        :type name: str
        :param machines: A list of machines for which the KPI data is requested.
        :type machines: list
        :param operations: A list of operations related to the KPI request.
        :type operations: list
        :param time_aggregation: The time aggregation method, such as 'min', 'max', 'mean', 'sum', 'var', or 'std'.
        :type time_aggregation: str
        :param start_date: The start date and time for the KPI data request (YYYY-MM-DD HH:MM:SS).
        :type start_date: datetime

        """
        self.name = name
        self.machines = machines
        self.operations = operations
        self.time_aggregation = time_aggregation
        self.start_date = start_date


class CustomKPICreationRequest(BaseModel):
    label: str
    superclass: str
    description: str
    unit_of_measure: str
    human_readable_formula: str
