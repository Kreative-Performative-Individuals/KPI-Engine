import ast
import re
import src.app.models.grammar as grammar


class ExpressionDisambiguator(ast.NodeVisitor):
    def __init__(self):
        self.result = ""

    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)

        op_str = get_operator_str(node.op)

        # If it's a * or / or ** operator, add parentheses around both sides
        if isinstance(node.op, (ast.Mult, ast.Div, ast.Pow)):
            # Add parentheses only if needed (i.e., avoid double parenthesis)
            if not isinstance(
                node.left, (ast.BinOp, ast.Call, ast.Attribute, ast.Compare)
            ):
                left = f"({left})"
            if not isinstance(
                node.right, (ast.BinOp, ast.Call, ast.Attribute, ast.Compare)
            ):
                right = f"({right})"
            self.result = f"({left}{op_str}{right})"
        else:
            self.result = f"({left}{op_str}{right})"

        return self.result

    def visit_Name(self, node):
        return node.id

    def visit_Constant(self, node):
        return str(node.value)

    def visit_Paren(self, node):
        # Handle existing parentheses, do not add extra parentheses
        return f"({self.visit(node)}"


def get_operator_str(op):
    if isinstance(op, ast.Mult):
        return "*"
    elif isinstance(op, ast.Div):
        return "/"
    elif isinstance(op, ast.Pow):
        return "**"
    elif isinstance(op, ast.Add):
        return "+"
    elif isinstance(op, ast.Sub):
        return "-"
    return ""


def disambiguate_expression(expression: str) -> str:
    # Parse the expression into an AST
    tree = ast.parse(expression, mode="eval")
    disambiguator = ExpressionDisambiguator()

    # Visit the tree nodes to disambiguate
    return disambiguator.visit(tree.body)


def translate_agg(agg, body):
    # Aggregation operation
    return f"A°{agg}°mo[{body}]"


def translate_op(op, left, right):
    # Arithmetic operations
    return f"S°{op}[{left} ; {right}]"


def translate_kpi_ref(kpi):
    # KPI reference rule
    return f"R°{kpi}°T°m°o°"


def translate_variable(var):
    # Variables rule
    return f"{var}°"


def get_first_operation(formula):
    count = 0
    for idx, char in enumerate(formula):
        if char == "(":
            count += 1
        elif char == ")":
            count -= 1
        elif count == 0:
            if formula[idx : idx + 2] == "**":
                return idx, idx + 2
            if char in grammar.operators:
                return idx, idx + 1
    return -1, -1


def translate_formula(formula):
    formula = formula.strip()

    # First, match aggregation formulas
    for agg in grammar.aggregations:
        match = re.match(rf"{agg}(.*)", formula)
        if match:
            return translate_agg(
                agg, translate_formula(disambiguate_expression(match.group(1)))
            )

    if formula.startswith("(") and formula.endswith(")"):
        formula = formula[1:-1]

    # get the first operation in the formula that occurs after the number of opening brackets is equal to the number
    # of closing brackets
    first_op_idx_start, first_op_idx_end = get_first_operation(formula)
    if first_op_idx_start != -1:
        left = formula[:first_op_idx_start]
        right = formula[first_op_idx_end:]

        left_translated = translate_formula(left)
        right_translated = translate_formula(right)

        # Return the operation translated with left-side recursion
        return translate_op(
            formula[first_op_idx_start:first_op_idx_end],
            left_translated,
            right_translated,
        )

    # Otherwise, check for database values, KPI references, or variables
    # If it's a number, translate to C°number°
    if formula.isdigit():
        return f"C°{formula}°"

    # Check if the formula is a valid KPI reference (assume alphabetic strings are KPI references)
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", formula):
        return translate_kpi_ref(formula)

    return formula
