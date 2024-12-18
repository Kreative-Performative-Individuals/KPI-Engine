""" This module defines the FastAPI endpoint for the KPI computation. """

from fastapi import APIRouter, HTTPException

from app.kpi_engine.dynamic.dynamic_engine import compute
from app.models.requests.rag import KPIRequest
from app.models.responses.rag import KPIResponse

router = APIRouter()


@router.post("/", response_model=KPIResponse)
async def get_kpi(
    request: KPIRequest,
) -> KPIResponse:
    """
    Computes a KPI based on the provided request.

    This endpoint performs the computation of a KPI using the provided parameters
    in the `KPIRequest` model. It will call the `compute` function from the dynamic
    engine to process the request and return the result as a `KPIResponse`. If there
    is an error during the computation, an appropriate HTTP exception is raised.

    :param request: The input parameters required to compute the KPI.
    :type request: :class:`KPIRequest`
    :return: The computed KPI result, encapsulated in a `KPIResponse`.
    :rtype: :class:`KPIResponse`
    :raises HTTPException:
        - If the computation fails due to invalid input (ValueError), raises a 404 status with the error message.
        - If an unexpected error occurs, raises a 500 status with a generic "Internal Server Error" message.
    """
    try:
        return compute(request, chart=False)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/chart", response_model=KPIResponse)
async def get_kpi_chart(
    request: KPIRequest,
) -> KPIResponse:
    """
    This function returns the KPI calculation from a `KPIRequest` object in a format suitable for a chart.
    It is similar to the :func:`get_kpi <src.app.kpi_engine.dynamic.dynamic_engine.compute>` function,
    but it returns the data as a time series, between the start and end dates of the request.

    :param request: The details of the KPI request including name, machines, operations, and time range.
    :type request: KPIRequest
    :return: The computed KPI data for the chart.
    :rtype: KPIResponse
    :raises HTTPException: Raises a 404 error if the request is invalid or a 500 error for internal server issues.
    """
    try:
        return compute(request, chart=True)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")
