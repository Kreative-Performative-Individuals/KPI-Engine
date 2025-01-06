import json
from typing import Optional


class KPIData:
    superclass: str
    label: str
    description: str
    unit_of_measure: str
    parsable_computation_formula: str
    human_readable_formula: Optional[str] = None  # Optional field, can be None
    depends_on_machine: bool = False  # Default value set to False
    depends_on_operation: bool = False  # Default value set to False

    def __init__(
        self,
        superclass,
        label,
        description,
        unit_of_measure,
        parsable_computation_formula,
        human_readable_formula=None,
        depends_on_machine=False,
        depends_on_operation=False,
    ):
        """
        Constructor method for initializing the KPIData object.

        :param superclass: The superclass of the KPI.
        :type superclass: str
        :param label: The label of the KPI.
        :type label: str
        :param description: The description of the KPI.
        :type description: str
        :param unit_of_measure: The unit of measure for the KPI.
        :type unit_of_measure: str
        :param parsable_computation_formula: The parsable computation formula for the KPI.
        :type parsable_computation_formula: str
        :param human_readable_formula: The human-readable formula for the KPI.
        :type human_readable_formula: str
        :param depends_on_machine: Whether the KPI depends on a machine.
        :type depends_on_machine: bool
        :param depends_on_operation: Whether the KPI depends on an operation.
        :type depends_on_operation: bool
        """
        self.superclass = superclass
        self.label = label
        self.description = description
        self.unit_of_measure = unit_of_measure
        self.parsable_computation_formula = parsable_computation_formula
        self.human_readable_formula = human_readable_formula
        self.depends_on_machine = depends_on_machine
        self.depends_on_operation = depends_on_operation

    def to_json(self):
        """
        Converts the KPIData object to a JSON string.

        :return: A JSON string representation of the KPIData.
        :rtype: str
        """
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)
