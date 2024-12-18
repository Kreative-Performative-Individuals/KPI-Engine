import requests
from app.models.requests.data_processing import KPIStreamingRequest


def connect_to_publisher(kpi_streaming_request: KPIStreamingRequest):
    """
    Connects to a data producer and starts real-time data processing.

    This function sends a POST request to a data preprocessing service, providing
    a `KPIStreamingRequest` object as the request body. The function attempts to
    start the real-time processing of KPI data by invoking the corresponding API
    endpoint.

    :param kpi_streaming_request: A `KPIStreamingRequest` object containing the data
                                  for the streaming request.
    :type kpi_streaming_request: KPIStreamingRequest
    :raises requests.exceptions.RequestException: If the request to the data
                                                 preprocessing service fails.
    :return: The JSON response from the data preprocessing service or an error message.
    :rtype: dict
    """
    try:
        response = requests.post(
            "http://data-preprocessing-container:8003/real-time/start",
            data=kpi_streaming_request.to_json(),
        )
        response.raise_for_status()  # Raise error for non-2xx responses
        return response.json()
    except Exception as e:
        print(f"Error connecting to producer: {e}")
        return {"Error": "Could not connect to producer"}
