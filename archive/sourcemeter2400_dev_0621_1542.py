
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

# GUESS OR FROM DEVICE DOCUMENTATION
NEWLINE = "\r"  # typically "\r", "\r\n" or "\n"

use_beeper      = False

SHORT_CIRC_CURR = 1e-8 # Define the Short Circuit Current

USE_GPIB = False

# %% Keithley Control: Classes
# =============================================================================
# CLASS FOR KEITHLEY CONTROL
# =============================================================================
class KeithleyError(Exception):
    """Custom exception to handle Keithley errors."""
    def __init__(self, message, location='',keithley_device=None):
        super().__init__(message)  # Pass the message to the base class
        self.location = location   # Store the location if provided

        # If an error is detected, try to turned off the Keithley
        if keithley_device:
            try:
                keithley_device.write_output('OFF')
            except:
                pass

    def __str__(self):
        # Provide a custom string representation of the error
        if self.location:
            return f"KeithleyError at {self.location}: {self.args[0]}"
        return f"KeithleyError: {self.args[0]}"
    
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
    # Panel selection
    panel = OptionSet(['Front', '1'], case_sensitive=False)
    panel_back = OptionSet(['Back', 'Rear', '0'], case_sensitive=False)

    # Source / Sense function selection
    voltage = OptionSet(['voltage', 'VOLT', 'V'], case_sensitive=False)
    current = OptionSet(['current', 'CURR', 'I'],case_sensitive=False)
    resistance = OptionSet(['resistance', 'RES', 'resist', 'R', 'RESI'], 
                           case_sensitive=False)

    # Output
    on = OptionSet(['On', '1'], case_sensitive=False)
    off = OptionSet(['Off', '0'], case_sensitive=False)

class KeithleyDebug:
    """
    Class to simulate Keithley and print command sent to this device.
    """
    def __init__(self):
        print('\n------------------------------')
        print('Keithley Connected:')
        print('------------------------------\n')
        self._closed = False

    def close(self):
        self._closed = True
        print("Keithley Closed")

    def write(self, cmd: str):
        if self._closed:
            raise RuntimeError("Cannot write: device is closed.")
        print(f"Write: {cmd}")

    def query(self, cmd: str):
        if self._closed:
            raise RuntimeError("Cannot query: device is closed.")
        print(f"Query: {cmd}")

        # ----- Checking Error Commands -----
        if cmd == "SYSTEM:ERROR?":
            return '0,"No error"\n'
        return None

class Sourcemeter2400Dev:
    """
    Class for low-level communications and operation of a Keithley SourceMeter
    in the 2400 series.
    """

    # ----- Connecting & Disconnecting Hardware -----
    def __init__(self,
                 port="COM1",  # on windows see device manager
                 debug=False,
                 cable="GPIB"):

        # Parameters to Connect Keithley
        self.port = port
        self.cable = cable

        # Debugging Parameters
        self.debug = debug
        self.debug_resistance = 50 # Ohm (to generate data)

        # Define keithley status variables
        self.keithley_connected = False
        self.keithley_busy      = False
        
        # Keithley name and information
        self.keithley      = None
        self.keithley_addr = None
        self.keithley_IDN  = None
        
        # Keithley settings
        self.comp_current = None
        self.comp_voltage = None
        self.sense        = None
        self.source       = None
        self.panel        = 'Front'

        # Create option registry
        self.options = OptionRegistry()
        
        # Define short circuit current
        self.short_circ_curr = SHORT_CIRC_CURR

        # Connect the keithley
        self.connect()

    
    def connect(self):
        """" Search for and connect to the Keithley by checking for GPIB """
        
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
            #print("Connected resources:", resources)

            # Check if Keithley 2425 is connected by filtering GPIB resources
            keithley_found = False
            for resource in resources:
                #print(resource)
                if "GPIB" in resource and "INSTR" in resource:
                    keithley_found = True
                    self.keithley_addr = resource
                    
                    # Connect to the Keithley 2425
                    self.keithley = rm.open_resource(self.keithley_addr)
                    
                    # Send *IDN? query to check communication with the instrument
                    self.keithley_IDN = self.keithley.query("*IDN?")
                    
                    # Mute the Keithley
                    if not use_beeper:
                        self.keithley.write(':SYST:BEEP:STAT OFF')
                    
                    # Record that the Keithley is connected
                    self.keithley_connected = True
                    break
            
            # Raise Error if a Keithley was not found.
            if not keithley_found:
                raise RuntimeError('Keithley not found.')
        # Connect using a R232 cable
        else:
            # TODO: FROM DEVICE DOCUMENTATION
            baudrate = 115200
            bytesize = 8
            parity = 'N'
            stopbits = 1
            xonxoff = False
            rtscts = True

            timeout = 1.0

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

    def reset(self):
        """
        Reset the device: Clear the status registers using *CLS. This includes 
        any errors from the instrument and the results board. Reset the GPIB 
        using *RST.
        """
        self.sense = None
        self.source = None
        self.keithley.write("*CLS")   # Clear the status registers
        self.keithley.write("*RST")   # Restore the GPIB Defaults
        self.check_error()            # Check for errors.
    
    def close(self):
        """ Close connection with the Keithley (if there is one connected). """
        if self.cable == "GPIB":
            # Turn off output source
            try:
                self.keithley.write("OUTP OFF")  # Turn on the output off.
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
            self.ser.close()

        print('Closed SourceMeter 2400 Device.')

    # ----- Writing & Querying General Commands -----

    def write(self, cmd: str):
        """Passes write commands to the keithley."""
        if self.debug:
            print("write:", repr(cmd))
        else:
            self.keithley.write(cmd)

    def query(self, cmd: str):
        """Passes query commands to the keithley."""
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

    def check_error(self, loc=''): # TODO Change to query_error
        """Check the Keithley for errors."""
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
        """Check to make sure Keithley is connected and ready."""
        if not self.keithley_connected:
            raise RuntimeError('No Keithley connected.')
        # if self.keithley_busy:
        #     raise RuntimeError('The Keithley is busy.')
        # if self.comp_current == None or self.comp_voltage == None:
        #     raise RuntimeError('No compliance current/voltage has been set.'+
        #                        ' Set values in "Keithley Setup" tab')
            
    def clear_registers(self):
        """
        Clear the status registers using *CLS. This includes any errors from 
        the instrument and the results board
        """
        self.keithley.write("*CLS")  # Clear the status registers


    def write_panel(self, panel:str):
        """
        Change the panel that is being used. Either 'Front' (1) or 'Back' (0).
        """
        # Set the panel depending on the option selected
        if self.options.front_panel.contains(panel):
            self.keithley.write(":ROUT:TERM FRONT")  # Selects the rear panel (default)
            self.check_error('Setting panel.')
            self.panel = 'Front'
        elif self.options.back_panel.contains(panel):
            self.keithley.write(":ROUT:TERM REAR") # Selects the front panel (default)
            self.check_error('Setting panel.')
            self.panel = 'Rear'
    
    
    # TODO: Fix this to write the compliance outright
    def write_compliance_current(self,comp_current):
        """Set the compliance (max) current for the Keithley in amps."""
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
        # Raise 
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
    def write_compliance_voltage(self,comp_voltage):
        """Set the compliance (max) voltage for the Keithley in amps."""
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
        # Raise 
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
        # Select the source
        if self.options.voltage.contains(source): # Source voltage
            # Write source command to Keithley
            self.keithley.write(":SOUR:FUNC VOLT")
            self.check_error()

            # Set the source range
            if source_range == 'Auto':
                self.keithley.write(":SOUR:VOLT:RANG:AUTO ON")
            else:
                self.keithley.write(":SOUR:VOLT:RANG:AUTO OFF")
                self.keithley.write(f":SOUR:VOLT:RANG {source_range}")

            self.check_error()

            # Save the source and range
            self.source = 'voltage'
            self.source_range = source_range

        elif self.options.current.contains(source): # Source current
            # Write source command to Keithley
            self.keithley.write(":SOUR:FUNC CURR")
            self.check_error()

            # Set the measurement range
            if source_range == 'Auto':
                self.keithley.write(":SOUR:CURR:RANG:AUTO ON")
            else:
                self.keithley.write(":SOUR:CURR:RANG:AUTO OFF")
                self.keithley.write(f":SOUR:CURR:RANG {source_range}")

            self.check_error()

            # Save the source
            self.source = 'current'
            self.source_range = source_range
        else:
            raise KeyError(f"Invalid input '{source}'.")
        
    # TODO: Add resistance sensing option at some point.
    def write_sense(self, sense, sense_range='Auto'):
        # Sensing Voltage
        if self.options.voltage.contains(sense): # Source voltage
            # Write source command to Keithley
            self.keithley.write(":SENS:FUNC VOLT")
            self.check_error()

            # Set the measurement range
            if sense_range == 'Auto':
                self.keithley.write(":SENS:VOLT:RANG:AUTO ON")
            else:
                self.keithley.write(":SENS:VOLT:RANG:AUTO OFF")
                self.keithley.write(f":SENS:VOLT:RANG {sense_range}")

            self.check_error()

            # Save the source and range
            self.sense = 'voltage'
            self.sense_range = sense_range
        
        # Sensing Current
        elif self.options.current.contains(sense):
            # Write source command to Keithley
            self.keithley.write(":SENS:FUNC 'CURR'")
            self.check_error()

            # Set the measurement range
            if sense_range == 'Auto':
                self.keithley.write(":SENS:CURR:RANG:AUTO ON")
            else:
                self.keithley.write(":SENS:CURR:RANG:AUTO OFF")
                self.keithley.write(f":SENS:CURR:RANG {sense_range}")

            self.check_error()

            # Save the source
            self.sense = 'current'
            self.sense_range = sense_range
        else:
            raise KeyError(f"Invalid input '{sense}'.")
        

    # ----- Writing DC Voltage and DC Current-----

    def write_voltage(self, voltage):
        if self.source == 'voltage':
            self.keithley.write(f"SOUR:VOLT {voltage}")
            self.check_error()
            
            if self.debug:
                # Save the setpoint if to generate simulated data
                self.voltage_setpt = voltage

        else:
            error_mssg = (
                'Attempt to write voltage without setting voltage as the ' 
                'source.'
            )
            raise KeithleyError(error_mssg)
        
    def write_current(self, current):
        if self.source == 'current':
            self.keithley.write(f"SOUR:VOLT {current}")
            self.check_error()

            if self.debug:
                # Save the setpoint if to generate simulated data
                self.current_setpt = current
        else:
            error_mssg = (
                'Attempt to write current without setting current as the ' 
                'source.'
            )
            raise KeithleyError(error_mssg)
        
    def write_NPLC(self,NPLC):
        if self.sense == 'current':
            # Change the integration for more accurate measurements
            self.keithley.write(f":SENS:CURR:NPLC {self.NPLC}")
            self.check_error()
        elif self.sense == 'voltage':
            # Change the integration for more accurate measurements
            self.keithley.write(f":SENS:VOLT:NPLC {self.NPLC}")
            self.check_error()

    
    # ----- Writing DC Voltage and DC Current-----

    def read_voltage(self):
        if self.sense == 'voltage':
            self.keithley.query("MEAS:VOLT:DC?")
            self.check_error()
        else:
            error_mssg = (
                'Attempt to read voltage without setting voltage sense.'
            )
            raise KeithleyError(error_mssg)
        
    def read_current(self):
        if self.sense == 'current':
            readout = self.keithley.query("MEAS:CURR:DC?")
            self.check_error('Read Current')
        
            # Parse the readout
            if self.debug:
                voltage = self.voltage_setpt
                current = self.voltage_setpt / self.debug_resistance
                current_err = 0
                resistance = self.debug_resistance
            else:
                voltage = float(readout.split(',')[0]) # Voltage in Volts
                current = float(readout.split(',')[1]) # Current in Amps
                resistance  = voltage / current if current != 0 else 0
                current_range = float(self.keithley.query(":SENS:CURR:RANG?"))
                current_err = 0
                # TODO: Add the current accuracy function.
                # current_err = current_accuracy("Measure", current_range, current)
            # print(f'Voltage: {voltage}')
            # print(f'Current: {current:.3e} +/- {current_err:.3e}')
            # print(f'Voltage Range: {self.keithley.query(":SOUR:VOLT:RANG?")}')
            # print(f'Current Range: {self.keithley.query(":SENS:CURR:RANG?")}\n')
        
            return voltage, current, current_err, resistance
        else:
            error_mssg = (
                'Attempt to read current without setting current sense.'
            )
            raise KeithleyError(error_mssg)

    def write_output(self,on_off):
        """
        Turn the output (voltage/current source) on or off.
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
    dev = Sourcemeter2400Dev(port="COM1",  # TODO: on windows see device manager
                             debug=False)
    
    # dev.check_status()
    dev.write_panel('Front')
    
    # Set the source in different ways
    print('\nSET SOURCE/SENSE')
    dev.write_source('Voltage',source_range='Auto')
    dev.write_sense('Current', sense_range='Auto')

    # dev.write_source('Voltage', source_range=1)
    # dev.write_sense('Current', sense_range=100e-3)

    # # Set the source in different ways
    # print('\nSET COMPLIANCES')
    # dev.write_compliance_current('1')  # 1 Amp
    # dev.write_compliance_voltage('10') # 10

    # Set voltage to zero before turning on
    print('\nPREPARE IV MEASUREMENT')
    dev.write_voltage(0)
    dev.write_output('ON')
    
    # ----- IV Measurement -----
    voltage_setpts = np.round(np.linspace(-1,1,5),4) # Create parameter space
    voltage_meas = [] # Create to store data points
    current_meas = [] # Create to store data points
    for i, voltage_setpt in enumerate(voltage_setpts):
        print(f'\nIV DATA POINT {i+1}')
        dev.write_voltage(voltage_setpt)
        time.sleep(0.2)

        (voltage, current, current_err, resistance) =  dev.read_current()

        voltage_meas.append(voltage)
        current_meas.append(current)

        print('Readout:')
        print(f'Voltage: {voltage:.2e} V, Current: {current:.2e} A')
    
    # Current an np.array from the data
    voltage_meas = np.array(voltage_meas)
    current_meas = np.array(current_meas)

    # Calculate the average resistance and compare to the debug resistance
    resistance_avg, b = np.polyfit(current_meas,voltage_meas,1)
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
