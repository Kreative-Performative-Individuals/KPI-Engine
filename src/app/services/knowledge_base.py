import requests

from app.models import exceptions


def get_kpi_formula(name: str) -> dict[str, str]:
    """
    Fetches the KPI formula from the knowledge base.

    This function makes a GET request to a knowledge base service to retrieve
    the formula for the specified KPI. If the KPI formula is not found,
    it raises a `KPIFormulaNotFoundException`.

    :param name: The name of the KPI for which the formula is requested.
    :type name: str
    :raises exceptions.KPIFormulaNotFoundException: If the KPI formula is not found in the knowledge base.
    :return: A dictionary containing the KPI formulas with keys as formula identifiers and values as formula strings.
    :rtype: dict[str, str]
    """
    response = requests.get(
        "http://kb-service-container:8001/kpi-formulas", params={"kpi": name}, timeout=5
    )
    if response.status_code != 200:
        raise exceptions.KPIFormulaNotFoundException()
    response = response.json()
    return response["formulas"]


def get_closest_kpi_formula(name: str) -> dict:
    """
    Fetches the closest matching KPI formula from the knowledge base.

    This function retrieves the closest matching KPI formula from the knowledge
    base for a given KPI name. If the formula cannot be found, it raises a
    `KPIFormulaNotFoundException`.

    :param name: The name of the KPI for which the closest formula is requested.
    :type name: str
    :raises exceptions.KPIFormulaNotFoundException: If the closest KPI formula is not found.
    :return: A dictionary containing the closest matching KPI formula.
    :rtype: dict
    """
    response = requests.get(
        "http://kb-service-container:8001/kpi-formulas", params={"kpi": name}, timeout=5
    )
    if response.status_code != 200:
        raise exceptions.KPIFormulaNotFoundException()
    return response.json()


def get_closest_instances(name: str) -> dict:
    """
    Fetches the closest class instances from the knowledge base.

    This function retrieves the closest matching class instances from the
    knowledge base for a given class name. If no instances are found, it raises
    a `KPIFormulaNotFoundException`.

    :param name: The name of the OWL class for which the closest instances are requested.
    :type name: str
    :raises exceptions.KPIFormulaNotFoundException: If the closest instances are not found.
    :return: A dictionary containing the closest matching class instances.
    :rtype: dict
    """
    response = requests.get(
        "http://kb-service-container:8001/class-instances",
        params={"owl_class_label": name},
        timeout=5,
    )
    if response.status_code != 200:
        raise exceptions.KPIFormulaNotFoundException()
    return response.json()
