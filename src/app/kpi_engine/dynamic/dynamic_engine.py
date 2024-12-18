""" This module contains the dynamic KPI engine, which processes KPI formulas and performs calculations based on the"""

from typing import Any

import re
import pandas as pd
import numpy as np
from nanoid import generate
import requests

import app.models.grammar as grammar
import app.models.exceptions as exceptions
from app.models.requests.rag import KPIRequest
from app.models.responses.rag import KPIResponse
from app.services.database import insert_aggregated_kpi
from app.services.knowledge_base import (
    get_kpi_formula,
    get_closest_instances,
    get_closest_kpi_formula,
)


def dynamic_kpi(
    kpi: str,
    formulas_dict: dict[str, str],
    partial_result: dict[str, Any],
    request: KPIRequest,
    **kwargs,
):
    """
    Processes a KPI formula string by evaluating and performing operations (D°, A°, S°, R°, C°) and resolving nested
    expressions. The function replaces parts of the string and recursively calls itself to process nested KPIs,
    returning the final computed result.

    :param kpi: The KPI formula string to be processed. It may contain nested expressions enclosed in square brackets
        and operations (D°, A°, S°, R°, C°).
    :type kpi: str
    :param formulas_dict: A dictionary containing predefined formulas or other necessary information for the KPI
        calculation.
    :type formulas_dict: dict
    :param partial_result: A partial result that is passed to calculation functions. It may contain intermediate data
        accumulated during processing.
    :type partial_result: any
    :param request: A KPIRequest object that may contain additional parameters required for processing, for example in the
        context of an API or web service.
    :type request: :class:`KPIRequest`
    :param kwargs: Additional arguments that can be passed to the function as needed.
    :type kwargs: dict, optional

    :raises KeyError: If an operation in the KPI string does not have a corresponding function in the global scope.
    :raises ValueError: If the formula contains invalid or unrecognized expressions.

    :return: The result of the calculated KPI formula, which can be a numeric value or other data type depending on the operation and the processed formula.
    :rtype: any
    """
    # find the body of the innermost wrapping of the formula with []
    pattern = re.compile(r"\[([^\[\]]*)]")
    match = pattern.search(kpi)

    # if we find a match we need to recursively calculate the inner content
    if match:

        inner_content = match.group(0)
        # where to save the partial results of the recursion
        output = []
        # case in which we match S°
        if ";" in inner_content:
            left, right = inner_content.split(";")
            # the [ and ] are kept
            left = re.sub(r"[\[\]]", "", left)
            right = re.sub(r"[\[\]]", "", right)
            output.append(
                dynamic_kpi(left, formulas_dict, partial_result, request, **kwargs)
            )
            output.append(
                dynamic_kpi(right, formulas_dict, partial_result, request, **kwargs)
            )

        # case in which we do not match S°
        else:
            part = re.sub(r"[\[\]]", "", inner_content)
            output.append(
                dynamic_kpi(part, formulas_dict, partial_result, request, **kwargs)
            )

        # substitute the inner content with the calculated value with a comma to avoid infinite recursion
        remaining_string = kpi.replace(
            inner_content, str(",".join(map(str, output))), 1
        )
        return dynamic_kpi(
            remaining_string, formulas_dict, partial_result, request, **kwargs
        )

    # else we have to discover if it is a D°, A°, S°, R° or C°

    # strip the kpi from the brackets
    kpi = re.sub(r"[\[\]]", "", kpi).strip()
    # get the first letter which is always the operation
    operation = kpi[0]

    # access the function by the operation
    function = globals()[operation]

    return function(
        kpi=kpi,
        partial_result=partial_result,
        formulas_dict=formulas_dict,
        request=request,
        **kwargs,
    )


def query_DB(kpi: str, request: KPIRequest, **kwargs) -> tuple[np.ndarray, np.ndarray]:
    """
    Queries the database for real-time data corresponding to a specific KPI, processes the data,
    and returns it in a split format based on the requested step.

    The function splits the data into steps for time aggregation, reshapes it into a 3D numpy array,
    and handles any remainder data by returning it separately.

    :param kpi: The KPI identifier, containing the name of the KPI and the database column reference.
    :type kpi: str
    :param request: The KPIRequest object containing the machines, operations, and time range for the query.
    :type request: KPIRequest
    :param kwargs: Additional keyword arguments (not used in this function but can be included for extensibility).
    :return: A tuple containing two numpy arrays:
             - `step_split`: A 3D numpy array representing the data split by the given step.
             - `bottom`: A numpy array containing the remainder of the data that doesn't fit into the step split.
    :rtype: tuple[np.ndarray, np.ndarray]
    :raises ValueError: If the KPI identifier is invalid and cannot be parsed.
    :raises requests.exceptions.RequestException: If the request to the database fails.
    :raises exceptions.EmptyQueryException: If the query returns no data.
    """
    kpi_split = kpi.split("°")[1]

    match = re.search(r"^(.*)_(.+)$", kpi_split)
    if match:
        before_last_underscore = match.group(1)
        after_last_underscore = match.group(2)
    else:
        raise ValueError(f"DB query - invalid DB reference: {kpi_split}")

    machines_to_send = ""
    for i in range(0, len(request.machines)):
        if i < len(request.machines) - 1:
            machines_to_send += request.machines[i] + ","
        else:
            machines_to_send += request.machines[i]

    operations_to_send = ""
    for i in range(0, len(request.operations)):
        if i < len(request.operations) - 1:
            operations_to_send += request.operations[i] + ","
        else:
            operations_to_send += request.operations[i]

    response = requests.get(
        "http://smart-database-container:8002/get_real_time_data",
        json={
            "start_date": str(request.start_date),
            "end_date": str(request.end_date),
            "kpi_name": before_last_underscore,
            "asset_id": "",
            "machines": machines_to_send,
            "operations": operations_to_send,
            "column_name": after_last_underscore,
        },
        timeout=10,
    )

    data = response.json()["data"]

    dataframe = pd.DataFrame(
        data,
        columns=["asset_id", "operation", "time", f"{after_last_underscore}"],
    )

    numpy_data = (
        dataframe.pivot(
            index="time",
            columns=["asset_id", "operation"],
            values=f"{after_last_underscore}",
        )
        .reset_index()
        .select_dtypes("number")
        .to_numpy()
    )

    if numpy_data.size == 0:
        raise exceptions.EmptyQueryException()

    step = request.step
    remainder = numpy_data.shape[0] % step
    bottom = None

    # the step splits perfectly
    if remainder == 0:
        step_split = numpy_data.reshape(
            numpy_data.shape[0] // step, step, numpy_data.shape[1]
        )
    # divide the numpy array in two parts, the first part is the step split and the second is the remainder
    else:
        # get the bottom part of the numpy array
        bottom = numpy_data[-remainder:]
        # bring it to three dimensions
        bottom = bottom.reshape(1, *bottom.shape)
        numpy_data = numpy_data[:-remainder]
        step_split = numpy_data.reshape(
            numpy_data.shape[0] // step, step, numpy_data.shape[1]
        )

    return step_split, bottom


def A(kpi: str, partial_result: dict[str, Any], **kwargs) -> str:
    """
    Performs an aggregation operation on a KPI, applying it to the data. The available aggregation are: mean, sum, max,
    min, var, std.

    :param kpi: The substring of the original formula matching the A° case of the grammar
    :type kpi: str
    :param partial_result: A dictionary containing intermediate results for KPIs, used for aggregation.
    :type partial_result: dict[str, Any]
    :param kwargs: Additional optional parameters that may be passed for extended functionality.
    :type kwargs: dict, optional
    :raises ValueError: If the variable for aggregation is not found in the list of supported aggregations.
    :return: A string representing the key for the aggregated KPI result.
    :rtype: str
    """
    keys_inv = keys_involved(kpi, partial_result)[0]

    # get the variable on which partial_result[key] should be aggregated
    var = kpi.split("°")[2]
    # if they match the outermost aggregation, we return the key
    if var == partial_result["agg_outer_vars"] or var == "m":
        return f"°{keys_inv}"

    # time aggregation on the split of step
    for aggregation in grammar.aggregations:

        if aggregation in kpi:

            if isinstance(partial_result[keys_inv], tuple):
                np_split, np_bottom = partial_result[keys_inv]
            else:
                np_split = partial_result[keys_inv]
                np_bottom = None

            # the queried dataframe is split perfectly by the step
            if np_bottom is None:
                result = getattr(np, "nan" + aggregation)(np_split, axis=1)
                partial_result[keys_inv] = result
                return f"°{keys_inv}"

            # handle the case in which the dataframe is split in two parts: aggregate and merge them
            result_split = getattr(np, "nan" + aggregation)(np_split, axis=1)
            result_bottom = getattr(np, "nan" + aggregation)(np_bottom, axis=1)
            partial_result[keys_inv] = np.concatenate(
                (result_split, result_bottom), axis=0
            )
            return f"°{keys_inv}"

    raise ValueError(
        f"Aggregation {var} not found in the list of aggregations. The list of aggregations is {grammar.aggregations}"
    )


# pairwise operation involving two elements
def S(kpi: str, partial_result: dict[str, Any], **kwargs):
    """
    Performs a binary operation between two KPIs, updating the partial result dictionary with the computed value.

    :param kpi: The substring of the original formula matching the S° case of the grammar
    :type kpi: str
    :param partial_result: A dictionary containing intermediate results for KPIs. It is updated with the result of the
        binary operation.
    :type partial_result: dict[str, Any]
    :param kwargs: Additional optional parameters for extended functionality.
    :type kwargs: dict, optional
    :raises InvalidBinaryOperatorException: If no valid binary operator is found in the list of operators.
    :return: The key representing the resulting KPI after the binary operation.
    :rtype: str
    """
    left, right = keys_involved(kpi, partial_result)

    op = next((op for op in grammar.operators if op in kpi), None)
    if op:
        # Perform the operation and update the partial result
        partial_result[left] = eval(f"partial_result[left] {op} partial_result[right]")
        return f"°{left}"

    raise exceptions.InvalidBinaryOperatorException(
        f"Binary operator not found in the list of operations: {grammar.operators}"
    )


def R(
    kpi: str,
    partial_result: dict[str, Any],
    formulas_dict: dict[str, str],
    request: KPIRequest,
    **kwargs,
):
    """
    Resolves a reference to another KPI by looking up the corresponding formula in the formulas dictionary and
        calculating it using the dynamic_kpi function.

    :param kpi: The substring of the original formula matching the R° case of the grammar
    :type kpi: str
    :param partial_result: A dictionary containing intermediate results for KPIs. It is updated with the result of the
        referenced KPI.
    :type partial_result: dict[str, Any]
    :param formulas_dict: A dictionary mapping KPI names to their corresponding formulas. Used to look up the formula
        for the referenced KPI.
    :type formulas_dict: dict[str, str]
    :param request: The associated KPIRequest, that provides a useful context in the resolution of this part.
    :type request: KPIRequest
    :param kwargs: Additional optional parameters for extended functionality.
    :type kwargs: dict, optional
    :raises InvalidFormulaReferenceException: If the referenced KPI formula is not found in the formulas dictionary.
    :return: The result of calculating the referenced KPI formula, as a string.
    :rtype: str
    """

    kpi_split = kpi.split("°")
    kpi_involved = kpi_split[1]
    operation = kpi_split[4]

    # save the operation if it is in the formula
    if operation in grammar.operations:
        partial_result.setdefault("internal_operation", []).append(operation)

    if kpi_involved in formulas_dict:
        return str(
            dynamic_kpi(
                formulas_dict[kpi_involved],
                formulas_dict,
                partial_result,
                request,
                **kwargs,
            )
        )

    raise exceptions.InvalidFormulaReferenceException(
        f"KPI {kpi} not found in the list of KPIs. The list of KPIs is {formulas_dict.keys()}"
    )


def D(
    kpi: str,
    partial_result: dict[str, Any],
    request: KPIRequest,
    **kwargs,
):
    """
    Executes a database query to retrieve data for a KPI and stores the results in the partial_result dictionary.

    :param kpi: The substring of the original formula matching the D° case of the grammar
    :type kpi: str
    :param partial_result: A dictionary containing intermediate results for KPIs. It is updated with the results from
        the database query.
    :type partial_result: dict[str, Any]
    :param request: The associated KPIRequest.
    :type request: KPIRequest
    :param kwargs: Additional optional parameters for extended functionality.
    :type kwargs: dict, optional
    :return: A string representing the key for the stored results in the partial_result dictionary.
    :rtype: str
    """
    if (
        "internal_operation" in partial_result
        and len(partial_result["internal_operation"]) != 0
    ):
        op = partial_result["internal_operation"].pop(0)
        if len(request.operations) != 0:
            request.operations = [op] * len(request.operations)
        elif len(request.machines) != 0:
            request.operations = [op] * len(request.machines)
        else:
            request.operations = [op]

    step_split, bottom = query_DB(kpi, request)
    key = generate(size=2)
    partial_result[key] = (step_split, bottom)
    return "°" + key


def C(kpi: str, partial_result: dict[str, Any], **kwargs):
    """
    Handles constant KPIs by storing a fixed value in the partial_result dictionary.

    :param kpi: The KPI formula representing a constant, where the constant value is provided after the '°'
        symbol (e.g., 'C°100').
    :type kpi: str
    :param partial_result: A dictionary containing intermediate results for KPIs. It is updated with the constant value
        extracted from the 'kpi' parameter.
    :type partial_result: dict[str, Any]
    :param kwargs: Additional optional parameters for extended functionality.
    :type kwargs: dict, optional
    :return: A string representing the key for the stored constant value in the partial_result dictionary.
    :rtype: str
    """
    key = generate(size=2)
    div = kpi.split("°")
    partial_result[key] = int(div[1])
    return "°" + key


def compute(request: KPIRequest, chart: bool) -> KPIResponse:
    """
    Computes the value of a KPI based on the given request, including the validation of machines and operations,
    fetching the corresponding formula from the knowledge base, and performing the necessary calculations and
    aggregation.

    :param request: The KPI request containing parameters such as KPI name, machines, operations, time range,
                    and time aggregation.
    :type request: :class:`KPIRequest`
    :param chart: Whether to return a times series or not
    :type chart: bool
    :return: A response containing a message with the computed result and the value of the KPI.
    :rtype: :class:`KPIResponse`
    :raises Exception: If an error occurs during the calculation process, such as invalid machines/operations,
                       failure to fetch the formula, or any computation errors.
    """

    name = request.name

    request.machines, request.operations = check_machine_operation(
        request.machines, request.operations
    )

    # get the formula from the KB
    try:
        formulas = get_kpi_formula(name)
        name = next(iter(formulas))

        if not formulas:
            formulas = get_closest_kpi_formula(name)
            formulas = formulas["formulas"]
            name = next(iter(formulas))

    except Exception as e:
        return KPIResponse(message=repr(e), value=-1)

    start_date = request.start_date
    end_date = request.end_date
    aggregation = request.time_aggregation

    # inits the kpi calculation by finding the outermost aggregation and involved aggregation variables
    partial_result = preprocessing(name, formulas)

    try:
        # computes the final matrix that has to be aggregated for mo and time_aggregation
        result = dynamic_kpi(formulas[name], formulas, partial_result, request)
    except Exception as e:
        return KPIResponse(message=repr(e), value=-1)

    # aggregated on time
    if not chart:
        result = finalize_mo(result, partial_result, request.time_aggregation)
    else:
        result = finalize_mo(result, partial_result, None)

    message = (
        f"The {aggregation} of KPI {name} for machines {request.machines} with operations {request.operations} "
        f"from {start_date} to {end_date} is {result}"
    )

    if not chart:
        _ = insert_aggregated_kpi(
            request=request,
            kpi_list=formulas.keys(),
            value=result,
        )

    return KPIResponse(message=message, value=result)


def preprocessing(kpi_name: str, formulas_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Preprocesses the KPI formula to extract aggregation variables and operations.

    :param kpi_name: The name of the KPI.
    :type kpi_name: str
    :param formulas_dict: Dictionary containing KPI formulas.
    :type formulas_dict: dict[str, Any]
    :return: A dictionary with aggregation variables and operations.
    :rtype: dict[str, Any]
    """
    partial_result = {}
    # get the actual formula of the kpi
    kpi_formula = formulas_dict[kpi_name]
    # get the variables of the aggregation
    search_var = kpi_formula.split("°")
    # split because we always have [ after the last match of the aggregation
    aggregation_variables = search_var[2].split("[")
    if search_var[1] in grammar.aggregations:
        partial_result["agg_outer_vars"] = aggregation_variables[0]
        partial_result["agg"] = search_var[1]
    else:
        partial_result["agg_outer_vars"] = ""
        partial_result["agg"] = ""

    return partial_result


def finalize_mo(
    final_formula: str, partial_result: dict[str, Any], time_aggregation: str
):
    """
    Finalizes the KPI calculation by applying the specified aggregation and time-based aggregation to the partial result.

    :param final_formula: The final formula representing the KPI, formatted as '°key', where 'key' corresponds to the
        key in the partial_result dictionary.
    :type final_formula: str
    :param partial_result: A dictionary containing partial results of KPIs. The key specified in 'final_formula' is used
        to access the corresponding data for aggregation.
    :type partial_result: dict[str, Any]
    :param time_aggregation: The time-based aggregation function to apply to the result (e.g., 'mean', 'sum').
    :type time_aggregation: str
    :return: The result of the aggregation after applying both the specified KPI aggregation and the time-based aggregation.
    :rtype: np.ndarray
    """
    # final formula is of the for '°key' where key is the key of the dictionary with the partial result
    key = final_formula.replace("°", "")
    result = partial_result[key]
    if partial_result["agg"] != "":
        result = getattr(np, "nan" + partial_result["agg"])(result, axis=1)
    if time_aggregation is None:
        return np.nan_to_num(result).tolist()
    return getattr(np, "nan" + time_aggregation)(result)


def keys_involved(kpi: str, partial_result: dict[str, Any]):
    """
    Extracts the keys involved in a KPI formula from the partial_result dictionary.

    :param kpi: The KPI formula represented as a string, which is split by the '°' symbol to extract the involved variables.
    :type kpi: str
    :param partial_result: A dictionary containing partial results for KPIs. The function checks which keys in the
        formula are present in this dictionary.
    :type partial_result: dict[str, Any]
    :return: A list of keys that are present in both the KPI formula and the partial_result dictionary.
    :rtype: list[str]
    """
    sep = kpi.split("°")
    if sep[0] == "S":
        sep[2] = sep[2].replace(",", "")
    result = [i for i in sep if i in partial_result]
    return result


def check_machine_operation(machines, operations):
    """
    Validates and adjusts the relationship between machines and operations.

    Ensures that the number of machines matches the number of operations.
    If a single machine string is provided, it resolves to the closest instances and adjusts the operations list if necessary.
    Handles mismatches by attempting reconciliation or returning an error response.

    :param machines: A string representing a single machine or a list of machine names.
    :type machines: str or list
    :param operations: A list of operations associated with the machines.
    :type operations: list
    :return: A tuple of validated and adjusted machines and operations or an error response.
    :rtype: tuple or KPIResponse
    :raises Exception: If resolving a machine string to its instances fails.
    """
    if isinstance(machines, str):
        try:
            machines = '"' + machines + '"'
            machine = get_closest_instances(machines)["instances"]
        except Exception as e:
            return KPIResponse(message=repr(e), value=-1)

        if machine:
            if len(machine) == len(operations):
                return machine, operations
            elif len(machine) < len(operations):
                return KPIResponse(
                    message="Invalid number of machines and operations", value=-1
                )
            else:
                operations.extend(["independent"] * (len(machine) - len(operations)))
                if len(machine) == len(operations):
                    return machine, operations
                else:
                    return KPIResponse(
                        message="Invalid number of machines and operations", value=-1
                    )
        return machine, operations

    if machines and operations:
        if len(machines) != len(operations):
            return KPIResponse(
                message="Invalid number of machines and operations", value=-1
            )
        return machines, operations

    return machines, operations
