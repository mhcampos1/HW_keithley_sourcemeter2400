'''
Created on Jul 16, 2026

@author: Misael Campos
'''
# from time import time

from ScopeFoundry.hardware import HardwareComponent

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

class Sourcemeter2400HW(HardwareComponent):

    name = "sourcemeter2400"

    def setup(self):
        S = self.settings

        # Connection Settings
        S.New("GPIB Addr", str, initial="5",
              description='COMx see device manager')

        # Compliance Current
        S.New("compliance_current", float, initial = 1, ro=False, unit='A', si=True,
               description='Maximum allowed current.')

        # Compliance Voltage
        S.New("compliance_voltage", float, initial = 10, ro=False, unit='V', si=True,
              description='Maximum allowed voltage.')

        # Input/Output Panel on the SourceMeter
        panel_choices = (
            ('Front', 'Front'), 
            ('Back', 'Back'), 
        )

        S.New("panel", str, ro=False, choices=panel_choices,
              description= "Front or rear input/output panel.")

        # Input/Output Panel on the SourceMeter
        S.New("beeper", bool, initial=False, ro=False,
                description= "Unmute/mute the beeper on the Keithley.")


        # Save the options registry
        self.options = OptionRegistry()

    def connect(self):
        """
        ScopeFoundry HardwareComponent for controlling Keithley 2400 Series
        SourceMeter from within a ScopeFoundry application.

        Connect to this ScopeFoundry HardwareComponent to the low-level
        device commmunication class Sourcemeter2400Dev. Create a LoggedQuanity
        (LQ) for each property, which is an LQCollection object called 
        "settings". For each LQ bind read and/or write functions to a setting 
        (sometimes only one is applicable).
        
        Template:
        S.get_lq("").connect_to_hardware(
            read_func=self.dev.read_,
            write_func = self.dev.write_
        )
        """
        S = self.settings

        from .sourcemeter2400_dev import Sourcemeter2400Dev
        self.dev = Sourcemeter2400Dev(S["GPIB Addr"], debug=S['debug_mode'])

        S.get_lq("panel").connect_to_hardware(
            #TODO: read_func=self.dev.write_panel,
            write_func = self.dev.write_panel
        )
        
        # Compliance Current
        S.get_lq("compliance_current").connect_to_hardware(
            #TODO: read_func=self.dev.read_compliance_current, 
            write_func=self.dev.write_compliance_current
        )

        # Compliance Voltage
        S.get_lq("compliance_voltage").connect_to_hardware(
             #TODO: read_func=self.dev.read_compliance_voltage,
            write_func=self.dev.write_compliance_voltage
        )

        S.get_lq("beeper").connect_to_hardware(
            #TODO: read_func=self.dev.write_panel,
            write_func = self.dev.write_beeper
        )

    def disconnect(self):
        if not hasattr(self, 'dev'):
            return

        # self.settings.disconnect_all_from_hardware()
        self.dev.close()
        del self.dev

    def start_measurement(self, source, sense, NPLC, source_range='Auto',
                          sense_range='Auto'):
        # Reset the Keithley
        self.dev.reset()

        # Set the source and sense
        self.dev.write_source(source, source_range)
        self.dev.write_sense(sense, sense_range)

        # Rewrite the beeper setting
        self.dev.write_beeper(self.settings["beeper"])

        # Write the compliances
        self.dev.write_compliance_voltage(self.settings["compliance_voltage"])
        self.dev.write_compliance_current(self.settings["compliance_current"])

        # Write the NPLC for this measurement
        self.dev.write_NPLC(NPLC)

        # Set the source setpoint to zero and turn on the output
        if self.options.voltage.contains(source): # Source Voltage
            self.dev.write_voltage(0)
        elif self.options.voltage.contains(source): # Source Current
            self.dev.write_current(0)

    def write_voltage(self, voltage):
        self.dev.write_voltage(voltage)

    def write_current(self, current):
        self.dev.write_current(current)

    def read_voltage(self):
        return self.dev.read_voltage()

    def read_current(self):
        return self.dev.read_current()

    def write_output(self, on_off):
        self.dev.write_output(on_off)

        # self.dev.write_output("ON")

    # if you want to continuously update settings implement *run* method
    # def run(self):
    #     self.settings.property_x.read_from_hardware()
    #     time.sleep(0.1)
