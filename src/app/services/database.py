import numpy as np
import requests

from app.models.requests.rag import KPIRequest


def insert_aggregated_kpi(
    request: KPIRequest,
    kpi_list: list,
    value: np.float64,
):
    """
    Inserts the aggregated KPI result into the database.

    This function constructs an SQL `INSERT` query to store the aggregated KPI data
    into a database. It inserts details such as the KPI name, the aggregated value,
    the relevant machines and operations, and the list of KPIs involved in the aggregation.

    :param request: The KPI request containing details such as name, machines,
                    operations, and date range for the aggregation.
    :type request: KPIRequest
    :param kpi_list: A list of KPIs that were involved in the aggregation.
    :type kpi_list: list
    :param value: The aggregated KPI value calculated from the input KPIs.
    :type value: np.float64
    :return: The response from the database after insertion.
    :rtype: requests.Response
    """
    data = {
        "name": request.name,
        "aggregated_value": value.item(),
        "begin_datetime": str(request.start_date),
        "end_datetime": str(request.end_date),
        "kpi_list": list(kpi_list),
        "operations": request.operations,
        "machines": request.machines,
        "step": request.step,
    }

    print("Inserting aggregated KPI data into the database...", data)

    return requests.post(
        "http://smart-database-container:8002/insert_aggregated_kpi",
        json=data,
        timeout=5,
    )
