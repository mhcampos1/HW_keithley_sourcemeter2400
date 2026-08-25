'''
Created on Jul 16, 2026

@author: Misael Campos
'''

# GOAL OF THIS FILE IS TO HANDLE LOW LEVEL COMMUNICATION THROUGH A SERIAL PORT
# SHOULD BE INDEPENDENT OF ANY SCOPEFOUNDRY FUNCTIONALITY.
# RUN THIS FILE TO TEST CONNECTION, TESTING COMMANDS WHILE CHECK main()

import serial
import time

# Imported from KCtrl_controller
import pyvisa
import os
import time
from datetime import datetime
import numpy as np
import warnings

# Custom imports from the Utilites files
if __name__ == '__main__':
    from sourcemeter2400_dev_utils import (
            SourcemeterSpecifications, 
            OptionSet,
            OptionRegistry,
            convert_current_to_float,
            convert_voltage_to_float
        )
else:
    from .sourcemeter2400_dev_utils import (
        SourcemeterSpecifications, 
        OptionSet,
        OptionRegistry,
        convert_current_to_float,
        convert_voltage_to_float
    )

# GUESS OR FROM DEVICE DOCUMENTATION
NEWLINE = "\r"  # typically "\r", "\r\n" or "\n"

# If True, the instrument may emit beeps (model-dependent).
use_beeper = False

# Short circuit current used for debug/simulation defaults.
SHORT_CIRC_CURR = 1e-8  # Define the Short Circuit Current

# Set to True to use GPIB transport instead of serial (if implemented).
USE_GPIB = True

# Overide Debug Input to Force Debug Mode
FORCE_DEGUG = True

# %% Keithley Control: Classes
# =============================================================================
# CLASS FOR KEITHLEY CONTROL
# =============================================================================
class KeithleyError(Exception):
    """Custom exception to handle Keithley errors."""

    def __init__(self, message, location='', keithley_device=None):
        """Initialize the KeithleyError.

        Args:
            message: Error message returned by the instrument.
            location: Optional context string describing where the error
                occurred (e.g., the command or operation).
            keithley_device: Optional Keithley device instance. If provided,
                an attempt is made to turn the device output OFF upon error.
        """
        super().__init__(message)  # Pass the message to the base class
        self.location = location   # Store the location if provided

        # If an error is detected, try to turned off the Keithley
        if keithley_device:
            try:
                keithley_device.write_output('OFF')
            except:
                pass

    def __str__(self):
        """Return a formatted string representation of the error."""
        # Provide a custom string representation of the error
        if self.location:
            return f"KeithleyError at {self.location}: {self.args[0]}"
        return f"KeithleyError: {self.args[0]}"


class KeithleyDebug:
    """Class to simulate Keithley and print commands sent to this device."""

    def __init__(self):
        """Initialize the debug simulator."""
        print('\n------------------------------')
        print('Keithley Connected:')
        print('------------------------------\n')
        self._closed = False

    def close(self):
        """Mark the simulated device as closed."""
        self._closed = True
        print("Keithley Closed")

    def write(self, cmd: str):
        """Simulate a write command to the device.

        Args:
            cmd: Command string.
        """
        if self._closed:
            raise RuntimeError("Cannot write: device is closed.")
        #print(f"Write: {cmd}")

    def query(self, cmd: str):
        """Simulate a query command to the device.

        Args:
            cmd: Query string.

        Returns:
            A simulated response string (or None if not a recognized query).
        """
        if self._closed:
            raise RuntimeError("Cannot query: device is closed.")

        # ----- Checking Error Commands -----
        if cmd == "SYSTEM:ERROR?":
            return '0,"No error"\n'
        else:
            # print(f"Query: {cmd}")
            pass
        return None


class Sourcemeter2400Dev:
    """Low-level communications and operation of a Keithley SourceMeter 2400.

    This class provides basic configuration and measurement methods for a
    Keithley SourceMeter series device. It supports either a VISA/GPIB path
    (via pyvisa) when ``cable == 'GPIB'`` or a serial placeholder path otherwise.
    """

    # ----- Connecting & Disconnecting Hardware -----
    def __init__(self,
                 addr="05",  # on windows see device manager
                 debug=False,
                 cable="GPIB"):
        """Create the device wrapper and connect immediately.

        Args:
            port: Serial port name (used only when not using GPIB).
            debug: If True, use a simulated Keithley device (KeithleyDebug).
            cable: Transport type. Expected values include 'GPIB' (pyvisa)
                or other value for serial mode.
        """
        # Parameters to Connect Keithley
        self.addr  = addr
        self.cable = cable

        # Debugging Parameters
        self.debug = debug
        self.debug_resistance = 9.744e3  # Ohm (to generate data)

        # Define keithley status variables
        self.keithley_connected = False
        self.keithley_busy = False

        # Keithley name and information
        self.keithley = None
        self.keithley_addr = None
        self.keithley_IDN = None

        # Keithley settings (tracked in software)
        self.comp_current = None
        self.comp_voltage = None
        self.sense = None
        self.source = None
        self.panel = 'Front'

        # Create option registry
        self.options = OptionRegistry()

        # Define short circuit current
        self.short_circ_curr = SHORT_CIRC_CURR

        # Connect the keithley
        self.connect()

    def connect(self):
        """Search for and connect to the Keithley.

        - If debug mode is enabled, a simulated Keithley is used.
        - If ``self.cable == 'GPIB'``, discovery is attempted via VISA:
          it scans VISA resources for an instrument matching typical
          GPIB-INSTR patterns and then uses *IDN? for verification.
        - Otherwise, it attempts to create a serial connection (parameters are
          placeholders based on device documentation expectations).
        """
        """" Search for and connect to the Keithley by checking for GPIB """
        # Force Debug Mode Regardless of Input (Change at the top of script)
        if FORCE_DEGUG:
            self.debug = True
        
        # Debugging mode
        if self.debug:
            self.keithley = KeithleyDebug()
            self.keithley_connected = True

        # Connect to keithley using GPIB
        elif self.cable == 'GPIB':
            # Create a ResourceManager instance
            rm = pyvisa.ResourceManager()

            # List all connected instruments
            resources = rm.list_resources()
            # print("Connected resources:", resources)

            # Check if Keithley 2425 is connected by filtering GPIB resources
            keithley_found = False
            for resource in resources:
                # print(resource)
                if f"GPIB0::{self.addr}::INSTR" in resource:
                # if "GPIB" in resource and "INSTR" in resource:
                    keithley_found = True
                    self.keithley_addr = resource

                    # Connect to the Keithley 2425
                    self.keithley = rm.open_resource(self.keithley_addr)

                    # Send *IDN? query to check communication with the instrument
                    self.keithley_IDN = self.keithley.query("*IDN?")

                    # Mute the Keithley (if supported and desired)
                    if not use_beeper:
                        self.keithley.write(':SYST:BEEP:STAT OFF')

                    # Record that the Keithley is connected
                    self.keithley_connected = True

                    print('Keithley Connected:')
                    print(f'Address: {self.keithley_addr}')
                    print(f"IDN: {self.keithley_IDN}")
                    break

            # Raise Error if a Keithley was not found.
            if not keithley_found:
                raise RuntimeError('Keithley not found.')

        # Connect using a R232 cable (serial mode)
        else:
            raise KeithleyError('R232 cable not supported yet.')
            # TODO: FROM DEVICE DOCUMENTATION
            baudrate = 115200
            bytesize = 8
            parity = 'N'
            stopbits = 1
            xonxoff = False
            rtscts = True

            timeout = 1.0

            # Create serial connection
            self.ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                xonxoff=xonxoff,
                rtscts=rtscts,
                timeout=timeout
            )

            # TODO: Edit this piece of code to make sure the keithley is
            # actually connected
            # Record that the Keithley is connected
            self.keithley_connected = True

        # Detect the model and store the specifcations

    def reset(self):
        """Reset the device.

        Clears the status registers using *CLS. This includes any errors from
        the instrument and the results board. Reset the GPIB using *RST.

        Note:
            This method assumes ``self.keithley`` implements ``write``.
        """
        self.sense = None
        self.source = None
        self.keithley.write("*CLS")   # Clear the status registers
        self.keithley.write("*RST")   # Restore the GPIB Defaults
        self.check_error()            # Check for errors.

    def close(self):
        """Close connection with the Keithley (if there is one connected)."""
        if self.cable == "GPIB":
            # Turn off output source
            try:
                self.keithley.write("OUTP OFF")  # Turn the output OFF.
            except:
                pass

            # Disconnect the Keithley
            try:
                self.keithley.close()
                self.keithley_connected = False
                self.keithley_busy = False
            except:
                pass
        else:
            # Close serial connection
            self.ser.close()

        print('Closed SourceMeter 2400 Device.')

    # ----- Writing & Querying General Commands -----

    def write(self, cmd: str):
        """Send a write command to the Keithley.

        Args:
            cmd: Command string to send.
        """
        if self.debug:
            print("write:", repr(cmd))
        else:
            self.keithley.write(cmd)

    def query(self, cmd: str):
        """Send a query command to the Keithley.

        Args:
            cmd: Query string to send.
        """
        if self.debug:
            print("query:", repr(cmd))
        else:
            self.keithley.query(cmd)

        # time.sleep(0.01)
        # if not TESTING_SOURCEMETER2400:
        #     resp: bytes = self.ser.readline()

        #     if self.debug:
        #         print("resp:", resp.decode())
        #     return resp.decode()

    # ----- General Maintenance -----

    def check_error(self, loc=''):
        """Check the Keithley for errors.

        Args:
            loc: Optional location/context string for error reporting.

        Raises:
            KeithleyError: If the device reports an error.
        """
        error = self.keithley.query("SYSTEM:ERROR?")

        # Check if there is an error and if the location is not specified
        if error != '0,"No error"\n':
            error_message = error.strip('\n')

            # If no location is provided, raise the error with the default message
            if loc == '':
                raise KeithleyError(error_message)

            # If location is provided, raise the error with the location
            else:
                raise KeithleyError(error_message, loc)

    def check_status(self):
        """Check to make sure Keithley is connected and ready.

        Raises:
            RuntimeError: If no Keithley is connected.
        """
        if not self.keithley_connected:
            raise RuntimeError('No Keithley connected.')
        # if self.keithley_busy:
        #     raise RuntimeError('The Keithley is busy.')
        # if self.comp_current == None or self.comp_voltage == None:
        #     raise RuntimeError('No compliance current/voltage has been set.'+
        #                        ' Set values in "Keithley Setup" tab')

    def clear_registers(self):
        """Clear the device status registers using *CLS.

        Includes any errors from the instrument and the results board.
        """
        self.keithley.write("*CLS")  # Clear the status registers

    def write_panel(self, panel: str):
        """Change the routing panel between Front and Back.

        Args:
            panel: Desired panel selection (e.g., 'Front' or 'Back').
        """
        # Set the panel depending on the option selected
        if self.options.front_panel.contains(panel):
            self.keithley.write(":ROUT:TERM FRONT")  # Select FRONT panel
            self.check_error('Setting panel.')
            self.panel = 'Front'
        elif self.options.back_panel.contains(panel):
            self.keithley.write(":ROUT:TERM REAR")  # Select REAR panel
            self.check_error('Setting panel.')
            self.panel = 'Rear'

    # TODO: Fix this to write the compliance outright
    def write_compliance_current(self, comp_current):
        """Set the compliance (protection) current limit in amps.

        Args:
            comp_current: Compliance current limit.
        """
        # Set compliance if sourcing current
        if self.sense == 'current':
            # Set the compliance current (protection current) limit
            self.keithley.write(f":SENS:CURR:PROT {comp_current}")
            self.check_error('Writing compliance current.')

        # Set compliance if sensing current
        elif self.source == 'current':
            # Set the compliance current (protection current) limit
            self.keithley.write(f":SOUR:CURR:PROT {comp_current}")
            self.check_error('Writing compliance current.')

        # Otherwise, the device is not configured correctly for compliance
        else:
            print(
                "WARNING! Compliance current not set! Keitheley is not in "
                "appropriate current sensing or sourcing mode."
            )
            # warnings.warn(
            #     "Compliance current not set! Keitheley is not in appropriate "
            #     "current sensing or sourcing mode."
            # )

    # TODO: Fix this to write the compliance outright
    def write_compliance_voltage(self, comp_voltage):
        """Set the compliance (protection) voltage limit.

        Args:
            comp_voltage: Compliance voltage limit.
        """
        # Set compliance if sourcing voltage
        if self.sense == 'voltage':
            # Set the compliance voltage (protection voltage) limit
            self.keithley.write(f":SENS:VOLT:PROT {comp_voltage}")
            self.check_error('Setting the compliance voltage.')

        # Set compliance if sensing voltage
        elif self.source == 'voltage':
            # Set the compliance voltage (protection voltage) limit
            self.keithley.write(f":SOUR:VOLT:PROT {comp_voltage}")
            self.check_error('Setting the compliance voltage.')

        # Otherwise, the device is not configured correctly for compliance
        else:
            print(
                "WARNING! Compliance voltage not set! Keitheley is not in "
                "appropriate voltage sensing or sourcing mode."
            )
            # warnings.warn(
            #     "Compliance voltage not set! Keitheley is not in appropriate "
            #     "voltage sensing or sourcing mode."
            # )

    # ----- Writing Measurement/Source Properties -----

    def write_source(self, source, source_range='Auto'):
        """Configure the device source function (voltage or current).

        Args:
            source: Source function name (e.g., 'Voltage' or 'Current').
            source_range: Range selection. Use 'Auto' for auto-ranging.
        """
        # Select the source
        if self.options.voltage.contains(source):  # Source voltage
            # Write source command to Keithley
            self.keithley.write(":SOUR:FUNC VOLT")
            self.check_error()

            # Set the source range
            if source_range == 'Auto':
                self.keithley.write(":SOUR:VOLT:RANG:AUTO ON")
            else:
                source_range_float = convert_voltage_to_float(source_range) 
                self.keithley.write(":SOUR:VOLT:RANG:AUTO OFF")
                self.keithley.write(f":SOUR:VOLT:RANG {source_range_float}")

            self.check_error()

            # Save the source and range
            self.source = 'voltage'
            self.source_range = source_range

        elif self.options.current.contains(source):  # Source current
            # Write source command to Keithley
            self.keithley.write(":SOUR:FUNC CURR")
            self.check_error()

            # Set the measurement range
            if source_range == 'Auto':
                self.keithley.write(":SOUR:CURR:RANG:AUTO ON")
            else:
                source_range_float = convert_current_to_float(source_range)
                self.keithley.write(":SOUR:CURR:RANG:AUTO OFF")
                self.keithley.write(f":SOUR:CURR:RANG {source_range_float}")

            self.check_error()

            # Save the source
            self.source = 'current'
            self.source_range = source_range
        else:
            raise KeyError(f"Invalid input '{source}'.")

    # TODO: Add resistance sensing option at some point.
    def write_sense(self, sense, sense_range='Auto'):
        """Configure the device sense function (voltage or current).

        Args:
            sense: Sense function name (e.g., 'Voltage' or 'Current').
            sense_range: Range selection. Use 'Auto' for auto-ranging.
        """
        # Sensing Voltage
        if self.options.voltage.contains(sense):  # Source voltage
            # Write sense command to Keithley
            self.keithley.write(":SENS:FUNC VOLT")
            self.check_error()

            # Set the measurement range
            if sense_range == 'Auto':
                self.keithley.write(":SENS:VOLT:RANG:AUTO ON")
            else:
                sense_range_float = convert_voltage_to_float(sense_range)
                self.keithley.write(":SENS:VOLT:RANG:AUTO OFF")
                self.keithley.write(f":SENS:VOLT:RANG {sense_range_float}")

            self.check_error()

            # Save the source and range
            self.sense = 'voltage'
            self.sense_range = sense_range

        # Sensing Current
        elif self.options.current.contains(sense):
            # Write sense command to Keithley
            self.keithley.write(":SENS:FUNC 'CURR'")
            self.check_error()

            # Set the measurement range
            if sense_range == 'Auto':
                self.keithley.write(":SENS:CURR:RANG:AUTO ON")
            else:
                sense_range_float = convert_current_to_float(sense_range)
                self.keithley.write(":SENS:CURR:RANG:AUTO OFF")
                self.keithley.write(f":SENS:CURR:RANG {sense_range_float}")

            self.check_error()

            # Save the source
            self.sense = 'current'
            self.sense_range = sense_range
        else:
            raise KeyError(f"Invalid input '{sense}'.")

    # ----- Writing DC Voltage and DC Current -----

    def write_voltage(self, voltage):
        """Set the voltage source setpoint.

        Args:
            voltage: Voltage setpoint.
        """
        if self.source == 'voltage':
            # Set voltage output level
            self.keithley.write(f"SOUR:VOLT {voltage}")
            self.check_error()

            # In debug mode, store the setpoint for simulated readouts
            if self.debug:
                self.voltage_setpt = voltage

        else:
            error_mssg = (
                'Attempt to write voltage without setting voltage as the '
                'source.'
            )
            raise KeithleyError(error_mssg)

    def write_current(self, current):
        """Set the current source setpoint.

        Args:
            current: Current setpoint.
        """
        if self.source == 'current':
            # NOTE: This writes SOUR:VOLT even in current mode; left as-is
            # to avoid changing active code behavior.
            self.keithley.write(f"SOUR:VOLT {current}")
            self.check_error()

            # In debug mode, store the setpoint for simulated readouts
            if self.debug:
                self.current_setpt = current
        else:
            error_mssg = (
                'Attempt to write current without setting current as the '
                'source.'
            )
            raise KeithleyError(error_mssg)

    def write_NPLC(self, NPLC):
        """Set the integration time (NPLC) for measurements.

        Args:
            NPLC: Integration parameter for the device.
        """
        if self.sense == 'current':
            # Change the integration for more accurate measurements
            self.keithley.write(f":SENS:CURR:NPLC {NPLC}")
            self.check_error()
        elif self.sense == 'voltage':
            # Change the integration for more accurate measurements
            self.keithley.write(f":SENS:VOLT:NPLC {NPLC}")
            self.check_error()

    # ----- Reading DC Voltage and DC Current -----

    def read_voltage(self):
        """Read the measured DC voltage.

        Returns:
            Depends on device query parsing (currently no return implemented).

        Raises:
            KeithleyError: If voltage sense is not configured.
        """
        if self.sense == 'voltage':
            readout = self.keithley.query("MEAS:VOLT:DC?")
            self.check_error()
        else:
            error_mssg = (
                'Attempt to read voltage without setting voltage sense.'
            )
            raise KeithleyError(error_mssg)

    def read_current(self):
        """Read the measured DC current.

        Returns:
            Tuple of (voltage, current, current_err, resistance).

            - voltage: measured voltage in volts
            - current: measured current in amps
            - current_err: currently set to 0 (TODO: accuracy function)
            - resistance: computed resistance (V / I) in ohms
        """
        if self.sense == 'current':
            # Query current measurement
            readout = self.keithley.query("MEAS:CURR:DC?")
            self.check_error('Read Current')

            # Parse output
            if self.debug:
                # Simulate with a debug resistance model
                voltage = self.voltage_setpt
                current = self.voltage_setpt / self.debug_resistance
                current_err = 0
                resistance = self.debug_resistance
                time.sleep(0.025) # Simulate integration time
            else:
                # Parse real device readout (expected CSV-like format)
                voltage = float(readout.split(',')[0])  # Voltage in Volts
                current = float(readout.split(',')[1])  # Current in Amps
                resistance = voltage / current if current != 0 else 0

                current_range = float(self.keithley.query(":SENS:CURR:RANG?"))
                current_err = 0

                # TODO: Add the current accuracy function.
                # current_err = current_accuracy("Measure", current_range, current)

            return voltage, current, current_err, resistance
        else:
            error_mssg = (
                'Attempt to read current without setting current sense.'
            )
            raise KeithleyError(error_mssg)

    def write_output(self, on_off):
        """Turn the output (voltage/current source) on or off.

        Args:
            on_off: Desired output state ('ON'/'OFF', '1'/'0', case-insensitive).
        """
        if self.options.on.contains(on_off):
            # Before turning on, set setpoint to zero.
            # if self.source == 'voltage':
            #     self.keithley.write(f"SOUR:VOLT 0")
            # elif self.source == 'current':
            #     self.keithley.write(f"SOUR:CURR 0")
            self.keithley.write("OUTP ON")
            self.check_error()
        else:
            self.keithley.write("OUTP OFF")
            self.check_error()

    def write_beeper(self,on_off_bool:bool):
        if on_off_bool:
            self.keithley.write(':SYST:BEEP:STAT ON')
        else:
            self.keithley.write(':SYST:BEEP:STAT OFF') # Mute Keithley

    # def read_property_x(self):
    #     raise NotImplementedError
    #     # TYPICALLY:
    #     # resp = self.query(f'GET_PROPERTY_X_CMD {value}')
    #     # return 'convert_to_float(resp)'

    # def read_data(self):
    #     # NOTE read_data is a too generic function name
    #     raise NotImplementedError

    #     # TYPICALLY:
    #     # resp = self.query(f'GET_DATA_COMMAND {value}')
    #     # return a list of data points from resp.


if __name__ == '__main__':
    # Instantiate the device for a standalone connectivity/self-test.
    dev = Sourcemeter2400Dev(
        port="COM1",  # TODO: on windows see device manager
        debug=False,
    )

    # dev.check_status()
    dev.write_panel('Front')

    # Set the source in different ways
    print('\nSET SOURCE/SENSE')
    dev.write_source('Voltage', source_range='Auto')
    dev.write_sense('Current', sense_range='Auto')

    # dev.write_source('Voltage', source_range=1)
    # dev.write_sense('Current', sense_range=100e-3)

    # # Set the source in different ways
    # print('\nSET COMPLIANCES')
    # dev.write_compliance_current('1')  # 1 Amp
    # dev.write_compliance_voltage('10') # 10

    # Set voltage to zero before turning on output
    print('\nPREPARE IV MEASUREMENT')
    dev.write_voltage(0)
    dev.write_output('ON')

    # ----- IV Measurement -----
    # Create parameter space for IV sweep
    voltage_setpts = np.round(np.linspace(-1, 1, 5), 4)

    # Create containers to store data points
    voltage_meas = []
    current_meas = []

    for i, voltage_setpt in enumerate(voltage_setpts):
        print(f'\nIV DATA POINT {i+1}')
        dev.write_voltage(voltage_setpt)
        time.sleep(0.2)

        # Read measured values
        (voltage, current, current_err, resistance) = dev.read_current()

        # Store results for post-processing
        voltage_meas.append(voltage)
        current_meas.append(current)

        # Print the readout
        print('Readout:')
        print(f'Voltage: {voltage:.2e} V, Current: {current:.2e} A')

    # End the measurement
    dev.write_output('OFF')
    dev.close()
    
    # Convert lists to numpy arrays
    voltage_meas = np.array(voltage_meas)
    current_meas = np.array(current_meas)

    # Calculate the average resistance and compare to the debug resistance.
    # Fits a first-order polynomial V = R * I + b.
    resistance_avg, b = np.polyfit(current_meas, voltage_meas, 1)

    # Compute percent error relative to the debug resistance model.
    percent_error = (
        100 * (resistance_avg - dev.debug_resistance) / dev.debug_resistance
    )

    # Print the test results
    print('\nMEASUREMENT RESULTS')
    print('---------------------')
    print(f'Avg. Resistance: {resistance_avg:.2e} Ohm')
    print(f'Act. Resistance: {dev.debug_resistance:.2e} Ohm')
    print(f'Percent Error  : {percent_error:.2} %')

    print('\n \n')