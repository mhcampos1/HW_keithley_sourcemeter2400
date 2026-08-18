"""
This utilities script contains helper functions used in in
sourcemeter2400_dev.py
"""
import numpy as np
import math

###############################################################################
# %% IV Helper Functions
###############################################################################
def convert_voltage_to_float(voltage_str):
    """
    Converts a formatted voltage string using SI units into a float.
    """
    # Strip leading/trailing whitespace
    voltage_str = voltage_str.strip()

    # Define a dictionary to map units to their corresponding factors
    unit_factors = {
        'V': 1,        # Volts (base unit)
        'mV': 1e-3,    # Millivolt (1mV = 10^-3 V)
        'µV': 1e-6,    # Microvolt (1µV = 10^-6 V)
    }

    # Check if the input has a valid unit
    for unit in unit_factors:
        if voltage_str.endswith(' '+unit):
            # Extract the numeric part of the string
            number_part = voltage_str[:-len(unit)].strip()

            try:
                # Convert the number to float and multiply by the appropriate factor
                return round(float(number_part) * unit_factors[unit],8)
            except ValueError:
                raise ValueError(f"Invalid number format: {number_part}")

    # If no valid unit found, raise an error
    raise ValueError(f"Invalid unit in voltage string: {voltage_str}")
    
def convert_current_to_float(current_str):
    """
    Converts a formatted current string using SI units into a float.
    """
    # Strip leading/trailing whitespace
    current_str = current_str.strip()

    # Define a dictionary to map units to their corresponding factors
    unit_factors = {
        'A': 1,        # Amperes (base unit)
        'mA': 1e-3,    # Milliampere (1mA = 10^-3 A)
        'µA': 1e-6,    # Microampere (1µA = 10^-6 A)
        'nA': 1e-9,    # Nanoampere (1nA = 10^-9 A)
        'pA': 1e-12    # Picoampere (1pA = 10^-12 A) - Added this as an example
    }

    # Check if the input has a valid unit
    for unit in unit_factors:
        if current_str.endswith(' '+unit):
            # Extract the numeric part of the string
            number_part = current_str[:-len(unit)].strip()

            try:
                # Convert the number to float and multiply by the appropriate factor
                return float(number_part) * unit_factors[unit]
            except ValueError:
                raise ValueError(f"Invalid number format: {number_part}")

    # If no valid unit found, raise an error
    raise ValueError(f"Invalid unit in current string: {current_str}")

###############################################################################
# %% Keithley Specification 2425
###############################################################################

class SourcemeterSpecifications:
    """
    This class stores the current and voltage range specifications for various
    Keihtley 2400 series SourceMeters.
    """
    def __init__(self, model_num):
        self.model_num = str(model_num)

        if self.model_num == "2425":
            self.set_specs_2425()
        else:
            self.set_specs_2425()

    def set_specs_2425(self):
        # Voltage accuracy for each range:
        VOLTAGE_SPECS_2425 = [
            # Range, Programming Res., Source Acc., Measurement Res., Measurement Acc.
            ["200.000 mV", 5.000e-6, "0.02 + 600.000e-6", 1.000e-6, "0.012 + 300.000e-6"],
            ["2.00000 V", 50.000e-6, "0.02 + 600.000e-6", 10.000e-6, "0.012 + 300.000e-6"],
            ["20.0000 V", 500.000e-6, "0.02 + 2.400e-3", 100.000e-6, "0.015 + 1.000e-3"],
            ["100.0000 V", 2.500e-3, "0.02 + 12.000e-3", 1.000e-3, "0.015 + 5.000e-3"]
        ]
            
        # Current accuracy for each range:
        CURRENT_SPECS_2425 = [
            # Range, Programming Res., Source Acc., Measurement Res., Measurement Acc.
            ["10.0000 µA", 500.000e-12, "0.033% + 2.000e-9", 100.000e-12, "0.027% + 700.000e-12"],
            ["100.000 µA", 5.000e-9, "0.031% + 20.000e-9", 1.000e-9, "0.025% + 6.000e-9"],
            ["1.00000 mA", 50.000e-9, "0.034% + 200.000e-9", 10.000e-9, "0.027% + 60.000e-9"],
            ["10.0000 mA", 500.000e-9, "0.045% + 2.000e-6", 100.000e-9, "0.035% + 600.000e-9"],
            ["100.000 mA", 5.000e-6, "0.066% + 20.000e-6", 1.000e-6, "0.055% + 6.000e-6"],
            ["1.00000 A", 50.000e-6, "0.067% + 900.000e-6", 10.000e-6, "0.060% + 570.000e-6"],
            ["3.00000 A", 50.000e-6, "0.059% + 2.800e-3", 10.000e-6, "0.052% + 1.710e-3"]
        ]

        # Create a dictionary to store the data
        VOLTAGE_SPECS_DICT_2425 = {}
        VOLTAGE_RANGE_CHOICES = [('Auto', 'Auto')]

        # Populate the dictionary with string keys
        for row in VOLTAGE_SPECS_2425:
            keithley_range = row[0]  # Keep range as a string
            VOLTAGE_SPECS_DICT_2425[keithley_range] = {
                "Programming Resolution": row[1],
                "Source Accuracy": row[2],
                "Measurement Resolution": row[3],
                "Measurement Accuracy": row[4]
            }

            VOLTAGE_RANGE_CHOICES.append((keithley_range, keithley_range))

        # Create a dictionary to store the data
        CURRENT_SPECS_DICT_2425 = {}
        CURRENT_RANGE_CHOICES = [('Auto','Auto')]

        # Populate the dictionary with string keys
        for row in CURRENT_SPECS_2425:
            keithley_range = row[0]  # Keep range as a string
            CURRENT_SPECS_DICT_2425[keithley_range] = {
                "Programming Resolution": row[1],
                "Source Accuracy": row[2],
                "Measurement Resolution": row[3],
                "Measurement Accuracy": row[4]
            }

            CURRENT_RANGE_CHOICES.append((keithley_range,keithley_range))

        # Save the voltage and current specifications and range choices
        self.voltage_specs_dict    = VOLTAGE_SPECS_DICT_2425
        self.current_specs_dict    = CURRENT_SPECS_DICT_2425
        self.voltage_range_choices = tuple(VOLTAGE_RANGE_CHOICES)
        self.current_range_choices = tuple(CURRENT_RANGE_CHOICES)
        
if __name__ == "__main__":
    specs_2425 = SourcemeterSpecifications("2425")

    # Iterate over all ranges in CURRENT_SPECS_DICT
    print("\n"*5)
    print("*" * 40)
    print(f"Keithley Model: {specs_2425.model_num} Voltage Ranges")
    print("*" * 40)
    print("Voltage range choices:")
    print(specs_2425.voltage_range_choices)
    print("-" * 40)
    for measurement_range, specs in specs_2425.voltage_specs_dict.items():
        print(f"Measurement Range: {measurement_range}")
        print(f"  Programming Resolution: {specs['Programming Resolution']}")
        print(f"  Source Accuracy: {specs['Source Accuracy']}")
        print(f"  Measurement Resolution: {specs['Measurement Resolution']}")
        print(f"  Measurement Accuracy: {specs['Measurement Accuracy']}")
        print("-" * 40)  # Separator for readability

    # Iterate over all ranges in CURRENT_SPECS_DICT
    print("\n"*5)
    print("*" * 40)
    print(f"Keithley Model: {specs_2425.model_num} Current Ranges")
    print("*" * 40)
    print("Current range choices:")
    print(specs_2425.current_range_choices)
    print("-" * 40)
    for measurement_range, specs in specs_2425.current_specs_dict.items():
        print(f"Measurement Range: {measurement_range}")
        print(f"  Programming Resolution: {specs['Programming Resolution']}")
        print(f"  Source Accuracy: {specs['Source Accuracy']}")
        print(f"  Measurement Resolution: {specs['Measurement Resolution']}")
        print(f"  Measurement Accuracy: {specs['Measurement Accuracy']}")
        print("-" * 40)  # Separator for readability

    # # Example usage with string keys
    # if __name__ == "__main__":
    #     range_to_check = "200.000 mV"  # Correct key format
    #     parameter_to_check = "Programming Resolution"
    #     print(f"{parameter_to_check} for range {range_to_check}: {VOLTAGE_SPECS_DICT[range_to_check][parameter_to_check]}")
        
    #     parameter_to_check = "Measurement Accuracy"
    #     print(f"{parameter_to_check} for range {range_to_check}: {VOLTAGE_SPECS_DICT[range_to_check][parameter_to_check]}")

###############################################################################
# Classes to manage input options
###############################################################################

class OptionSet:
    """A set-like container for string options with optional case handling.

    This class supports fast membership checks. If ``case_sensitive`` is False,
    both stored options and queried elements are normalized to lowercase.
    """

    def __init__(self, options, *, case_sensitive=False):
        """Initialize the OptionSet.

        Args:
            options: Iterable of allowed option strings.
            case_sensitive: If True, comparisons are case-sensitive.
                If False, comparisons are case-insensitive by lowercasing
                both options and query values.

        Raises:
            TypeError: If options is not iterable.
        """
        self.case_sensitive = case_sensitive

        if case_sensitive:
            self._options = [str(option) for option in options]
        else:
            # Normalize options to lowercase for case-insensitive membership tests.
            self._options = [str(option).lower() for option in options]

    def contains(self, element):
        """Check whether an element exists in the allowed options.

        Args:
            element: The string (or value convertible to string) to check.

        Returns:
            True if the element is present in the allowed options; False otherwise.
        """
        if not self.case_sensitive:
            element = str(element).lower()
        return element in self._options

    def require(self, element):
        """Require that an element exists in the allowed options.

        Args:
            element: The string (or value convertible to string) to validate.

        Returns:
            True if the element is present.

        Raises:
            KeyError: If the element is not present in the allowed options.
        """
        if self.contains(element):
            return True

        raise KeyError(
            "Element not in the list of options. "
            f"Case sensitive: {self.case_sensitive}. "
            f"Options: {self._options}"
        )


class OptionRegistry:
    """Registry of valid option strings for the Keithley command mappings."""

    # Panel selection
    front_panel = OptionSet(['Front', '1'], case_sensitive=False)
    back_panel = OptionSet(['Back', 'Rear', '0'], case_sensitive=False)

    # Source / Sense function selection
    voltage = OptionSet(['voltage', 'VOLT', 'V'], case_sensitive=False)
    current = OptionSet(['current', 'CURR', 'I'], case_sensitive=False)
    resistance = OptionSet(
        ['resistance', 'RES', 'resist', 'R', 'RESI'],
        case_sensitive=False,
    )

    # Output
    on = OptionSet(['On', '1'], case_sensitive=False)
    off = OptionSet(['Off', '0'], case_sensitive=False)