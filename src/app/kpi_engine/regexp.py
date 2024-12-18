""" This module contains functions to clean and transform formulas for real-time evaluation. """

import re
from typing import Any
from app.models import exceptions
from app.services.knowledge_base import get_closest_kpi_formula, get_kpi_formula


def clean_placeholders(formulas: dict[str, str]) -> (dict[str, str], dict[int, str]):
    """
    Cleans the formulas by removing the placeholders used in the Knowledge Base (KB) and replacing them with specific
    operations such as 'idle', 'working', 'offline'. When one of these operations is encountered, it is saved in a separate list.

    The function iterates over each formula in the `formulas` dictionary and replaces the placeholders with their associated operations.
    The recognized placeholders are related to the activity states (idle, working, offline) and general placeholders like "°T°m°o°".

    :param formulas: A dictionary containing the formulas to clean. The keys are the names of the formulas, and the values are the formula strings.
    :type formulas: dict[str, str]

    :return: A tuple with two elements:
        - A dictionary containing the cleaned formulas, where the keys are the names of the formulas and the values are the formulas with placeholders removed.
        - A list containing the detected operations (e.g., "idle", "working", "offline").
    :rtype: tuple[dict[str, str], list[str]]
    """
    cleaned_formulas = {}
    formula_operations = {}

    # Define a pattern to match placeholders
    placeholder_pattern = re.compile(r"°[tT]°m°(idle|working|offline)°")

    # Iterate through the formulas dictionary
    for key, formula in formulas.items():
        match_count = 0

        # Find all matches of the pattern in the formula
        for match in placeholder_pattern.finditer(formula):
            match_count += 1
            operation = match.group(1)  # Extract the operation (working, idle, offline)
            formula_operations[match_count] = operation

        # Remove all matched placeholders from the formula
        cleaned_formula = placeholder_pattern.sub("", formula)

        # Remove other placeholders
        cleaned_formula = re.sub(r"°[tT]°m°o°", "", cleaned_formula)

        # Save the cleaned formula
        cleaned_formulas[key] = cleaned_formula.strip()

    return cleaned_formulas, formula_operations


def remove_aggregations(result: dict[str, str]) -> dict[str, str]:
    """
    Removes the A° aggregations from the formula and saves the outermost one.
    If there are binary operations, it transforms them into a numexpr-parsable formula.

    :param result: A dictionary containing the formula to clean. It includes:
        - 'formula': The formula string to clean.
        - 'agg': (Optional) The type of aggregation function found in the formula.
    :type result: dict[str, str]

    :return: The updated dictionary containing the cleaned formula with the outermost aggregation removed, and the aggregation type saved.
    :rtype: dict[str, str]
    """

    formula = result["formula"]

    formula = re.sub(r"°t", "", formula)
    formula = re.sub(r"°mo", "", formula)
    # replace with capital M to avoid matching max. min, ...
    formula = re.sub(r"A°m", "A°M", formula)
    #
    formula = re.sub(r"°m", "", formula)

    index = float("inf")

    agg_functions = ["A°sum[", "A°Mean[", "A°max[", "A°Min[", "A°var[", "A°std["]

    first_aggregation = None

    # until there are aggregations in the formula
    while any(agg_func in formula for agg_func in agg_functions):
        # do it for every possible aggregation sice we don't know the outermost one
        start_index = -1
        for agg_func in agg_functions:
            start_index = formula.find(agg_func)
            # if we find the aggregation in the formula
            if start_index != -1:
                # if the first aggregation has not been found, or if the current one is before the first one
                if first_aggregation is None or start_index < index:
                    index = start_index
                    # first aggregation is the first match
                    first_aggregation = agg_func.strip("A°[").lower()
                break

        # We interrupt immediately if we don't find anything
        if start_index == -1:
            break

        # we initialize a counter for the [ and ] in particular we increase if we find a [ and decrease if ] so we
        # delete the aggregation and the corresponding []
        depth = 1
        end_index = start_index + len(agg_func)

        # Here the implementation of the logic explained before
        for i, char in enumerate(formula[end_index:]):
            match char:
                case "[":
                    depth += 1
                case "]":
                    depth -= 1

            if depth == 0:
                end_index += i
                break

        # here we check if the ] is the last char of the formula then we return a new expression that starts from
        #  the next char after A°aggr[ and end at the last char before the ] and we have two cases :
        # the first if the ] is at the end of the expression
        # the second if th ] is in the middle of the expression
        if (len(formula) - 1) == end_index:
            formula = (
                formula[:start_index] + formula[start_index + len(agg_func) : end_index]
            )
        else:
            formula = (
                formula[:start_index]
                + formula[start_index + len(agg_func) : end_index]
                + formula[end_index + 1 :]
            )

        # remove external spaces
        formula = "".join(formula.split())

    result["formula"] = formula
    result["agg"] = first_aggregation
    return result


def to_evaluable(formula: str):
    """
    Transforms the expression in a parsable form for the numexpr library.
    It transforms the binary operations in a parsable form for the numexpr library.

    The function looks for specific operator patterns in the formula, converts them to the corresponding Python operators,
    and handles constants by replacing them with the actual numeric value.

    :param formula: The formula string to be transformed into a numexpr-compatible format.
    :type formula: str

    :return: The transformed formula as a string, formatted for numexpr evaluation.
    :rtype: str
    """
    # Map of the possible operator that we can find
    operator_map = ["S°/", "S°*", "S°+", "S°-", "S°**"]

    # we check for the possible S° operator, and we start from the outer one

    while any(op in formula for op in operator_map):
        start_index = -1
        for op in operator_map:
            start_index = formula.find(op + "[")
            print(start_index)
            if start_index != -1:
                break

        # if we don't find an operator
        if start_index == -1:
            break

        # we initialize a counter for the  [] parenthesis in increase the counter by one if we find [ and decrease
        # by one if we find a ] so when we find a ; and counter ==1 we substitute it with the operator, and then
        # we put () instead []
        depth = 1
        end_index = start_index + len(op) + 1
        semicolon_index = None

        for i, char in enumerate(
            formula[start_index + len(op) + 1 :], start=start_index + len(op) + 1
        ):
            match char:
                case "[":
                    depth += 1
                case "]":
                    depth -= 1
                case ";" if depth == 1:
                    semicolon_index = i

            if depth == 0:
                end_index = i
                break

        # substitute the most internal block with the operator
        if semicolon_index is not None:
            # substitute the semicolon with the operator
            formula = (
                formula[:start_index]
                + "("
                + formula[start_index + len(op) + 1 : semicolon_index]
                + f" {op[2]} "
                + formula[semicolon_index + 1 : end_index]
                + ")"
                + formula[end_index + 1 :]
            )

    # if we find a constant, remove C°[number]° with the number
    formula = re.sub(r"C°(\d+)°", r"\1", formula)
    return formula.strip()


def extract_names(formula_info: dict[str, Any]) -> list[str]:
    """
    Extracts variable names from an expression in the formula. The function identifies all alphanumeric sequences
    that represent variable names, ignoring pure numbers.

    :param formula_info: A dictionary containing the formula and associated operations.
    :type formula_info: dict
    :return: A list of names extracted from the formula, excluding pure numbers.
    :rtype: list[str]
    """
    expression = formula_info["formula"]
    operations = formula_info["operations_f"]
    # Pattern to find valid names: letters, numbers and underscore
    pattern = re.compile(r"\b[a-zA-Z_]\w*\b")  # we don't mach pure numbers
    names = pattern.findall(expression)

    formula_info["formula"] = replace_operations_in_formula(expression, operations)

    filtered_names = [name for name in names if not name.isdigit()]

    return filtered_names


def prepare_for_real_time(kpi_name: str) -> (list[str], dict[str, str]):
    """
    Retrieves the formula for a given KPI name from the knowledge base (KB), cleans and transforms the formula
    into a parsable form compatible with the numexpr library, and extracts the involved KPIs.

    :param kpi_name: The name of the KPI for which to retrieve the formula and transform.
    :type kpi_name: str

    :return: A tuple containing:
        - A list of KPI names that are involved in the formula.
        - A dictionary containing the transformed formula, ready for numexpr evaluation.
    :rtype: tuple[list[str], dict[str, str]]

    :raises KPIFormulaNotFoundException: If no formula could be found for the given KPI name.
    """
    try:
        response = get_kpi_formula(kpi_name)
        if response is None:
            # get the reference from the KB with the other method
            response = get_closest_kpi_formula(kpi_name)
            response = response["formulas"]

        cleaned_formulas, operations = clean_placeholders(response)
        most_general_formula_key = next(iter(cleaned_formulas))
        formula = cleaned_formulas[most_general_formula_key]  # most general formula
        evaluable_formula = transform_formula(formula, cleaned_formulas, operations)
        involved_kpis = extract_names(evaluable_formula)

    except exceptions.KPIFormulaNotFoundException() as e:
        print(f"Error getting KPI database references: {e}")
        return [], None

    return involved_kpis, evaluable_formula


def transform_formula(
    formula: str, formulas: dict[str, str], operation_IWO: dict[str:Any]
) -> dict[str, str]:
    """
    Takes a formula and its sub formulas and transforms it in a parsable form for the numexpr library.

    :param formula: The formula to be transformed.
    :type formula: str
    :param formulas: A dictionary of formulas, where the keys are formula names and the values are the actual formulas.
    :type formulas: dict[str, str]
    :param operation_IWO: A list of operations.
    :type operation_IWO: list[str]

    :return: A dictionary containing:
        - 'formula': The transformed formula that can be evaluated by numexpr.
        - 'operations_f': The operations found in the formula.
    :rtype: dict[str, str]
    """
    result = {"operations_f": operation_IWO}

    # save in the result the operations idle working offline, if present
    # we catch if the formula has a particular structure with no
    if not operation_IWO:
        result["particular"] = 0
    else:
        result["particular"] = 1
    # substitution of the R° references with their formula in the formulas dict
    formula = re.sub(r"R°(\w+)", lambda match: f"{formulas[match.group(1)]}", formula)
    # remove the D° from the formula
    formula = re.sub(r"D°(\w+)", r"\1", formula)

    # remove the spaces
    formula = "".join(formula.split())
    result["formula"] = formula
    # remove the inner aggregations after saving the outermost one
    result = remove_aggregations(result)

    # then if in the formula there are pairwise operation then transform in a parsable formula
    result["formula"] = to_evaluable(result["formula"])
    return result


def replace_operations_in_formula(formula: str, mapping: dict[int, str]) -> str:
    """
    Replaces placeholders in the formula based on a mapping of positions to operation types.

    :param formula: The formula string to modify.
    :type formula: str
    :param mapping: A dictionary mapping placeholder positions to operation types.
    :type mapping: dict[int, str]
    :return: The modified formula with placeholders replaced.
    """

    # Generalize replacement for variable names (alphanumeric and underscores) and append the operation suffix
    def replacement(match):
        keyword = match.group(0)  # Match the keyword (e.g., "time_sum")
        position = replacement.counter + 1
        replacement.counter += 1
        operation = mapping.get(position, "")
        return f"{keyword}_{operation}" if operation else keyword

    replacement.counter = 0

    # Match variable names (words starting with a letter or underscore and followed by word characters)
    formula = re.sub(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", replacement, formula)

    return formula
