"""
Created on Aug 16, 2026

@author: 
"""

import pyqtgraph as pg
from qtpy import QtCore, QtWidgets
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from ScopeFoundry import Measurement, h5_io

import numpy as np
import time

class InsituPulseReaction(Measurement):
    # -------------------------------------------------------------------------
    # %% SETUP:
        # Initialize the measurement settings
        # Define custom helper classes and initialize them.
    # -------------------------------------------------------------------------
    name = "insitu_pulse_reaction_readout"

    def setup(self):
        """
        Runs once during app initialization.
        This is where you define your settings, 
        and set up data structures.
        """
        s = self.settings

        # ----- Pulse Settings -----
        # Pulse Voltage
        s.New(
            "Pulse DC Voltage", float, initial=1, unit='V',si=True,
            description= ("DC voltage setpoint for heating(pulsing).")
        )
        s.New(
            "Pulse Width", float, initial=1, unit='s',si=True,
            description= ("Duration of the heating voltage pulse.")
        )
        s.New(
            "Pulse Meas. Delay", float, initial=0.15, unit='s',si=True,
            description= ("Time delay between electrical measurements.")
        )

        # ----- Reference -----
        # Reference Voltage
        s.New(
            "Reference DC Voltage", float, initial=0.1, unit='V',si=True,
            description= ("DC voltage for measuring the cold resistance.")
        )
        s.New(
            "Reference Width", float, initial=1, unit='s',si=True,
            description= ("Duration of the reference voltage pulse.")
        )
        s.New(
            "Reference Meas. Delay", float, initial=0.15, unit='s',si=True,
            description= ("Time delay between electrical measurements.")
        )

        # Voltage Stabilization Time
        s.New(
            "Voltage Stabilization Time", float, initial=0.2, unit='s',si=True,
            description= ("Time delay before taking a measurement after a new"
                          "voltage is applied.")
        )

        # Save h5 file
        s.New(
            "save_h5", bool, 
            initial=False
        )
        
        # Continuous
        s.New(
            "Continuous", bool, initial=False,
            description=("Enable continuous measuring without stoppage time.")
        )

        # Duration
        s.New(
            "Number of Cycles", int, initial=1,
            description= ("Number of cylces before stopping.")
        )

        # Number of Power Line Cycles (NPLC)
        s.New(
            "NPLC", float, initial=1, vmin=0.01, vmax=10,
            description=("Number of power line cycles (0.01-10)."
                         "Proportional to the integration time.")
        )

        meas_range_choices = (
            ('Auto', 'Auto'), 
            ('10.0000 µA', '10.0000 µA'), 
            ('100.000 µA', '100.000 µA'), 
            ('1.00000 mA', '1.00000 mA'), 
            ('10.0000 mA', '10.0000 mA'), 
            ('100.000 mA', '100.000 mA'), 
            ('1.00000 A', '1.00000 A'), 
            ('3.00000 A', '3.00000 A')
        )

        s.New("Meas. Range", str, choices=meas_range_choices)


        # Initialize the Data Manager
        self.dm = self.DataManager(self.name)
        
        # Initialize the signal worker
        self.sig_worker = self.SignalWorker()

        # Connect the signals to display update functions and progress update
        self.sig_worker.update_plot.connect(
            self.update_display, 
            QtCore.Qt.QueuedConnection
        )
        
        self.sig_worker.update_progress.connect(
            self.set_progress,
            QtCore.Qt.QueuedConnection
        )

    class Timer:
        """Custom class to record the current time in the measurement."""
        def start(self):
            self.start_time = time.time()

        def time(self):
            return time.time() - self.start_time

    class SignalWorker(QtCore.QObject):
        """
        Class to handle Qt.Signals. 
        """
        # Signal to update the plot for live data plotting
        update_plot = QtCore.Signal()

        # Signal to update the progess bar
        update_progress = QtCore.Signal(float)

        def __init__(self, parent=None):
            super().__init__(parent)


    # -------------------------------------------------------------------------
    # %% PLOTTING AND DATA MANAGEMENT:
    # -------------------------------------------------------------------------    
    class DataManager():
        """
        Handles data storage, configuration management, and rendering.
        Contains nested configuration classes to maintain a tight logical coupling.
        """

        @dataclass
        class SeriesConfig:
            """Configuration for an individual data series (a single line)."""
            x_data_name: str
            y_data_name: str
            label: str
            pen: str
            symbol_brush: str
            symbol_pen: str
            symbol: str = "o"
            symbol_size: int = 8
            depth: int = 1

        @dataclass
        class PlotConfig:
            """Configuration for a complete plot view and its axis."""
            x_label: str
            x_units: str
            y_label: str
            y_units: str
            x_autoscale : bool =  True
            y_autoscale : bool =  True
            series: List['DataManager.SeriesConfig'] = field(default_factory=list)

        class PlotRegistry:
            """Manages the collection of available plot configurations."""
            def __init__(self):
                self._configs: Dict[str, 'DataManager.PlotConfig'] = {}

            def add_plot(self, name: str, config: 'DataManager.PlotConfig'):
                self._configs[name] = config

            def get_all_names(self) -> List[str]:
                return list(self._configs.keys())

            def __getitem__(self, key):
                return self._configs[key]

        def __init__(self, name: str):
            self.name = name

            # Initialize the Registry inside the manager
            self.registry = self.PlotRegistry()
            self.registry.add_plot('Current', self.PlotConfig(
                x_label = 'Time', 
                x_units = 's', 
                y_label = 'Current', 
                y_units = 'A', 
                series = [
                    self.SeriesConfig(
                        x_data_name = 'ref. time', 
                        y_data_name = 'ref. current', 
                        label = 'Ref Current', 
                        pen = None,
                        symbol_brush = 'g',
                        symbol_pen = 'g', 
                    ),
                    self.SeriesConfig(
                        x_data_name = 'pulse time', 
                        y_data_name = 'pulse current', 
                        label = 'Pulse Current', 
                        pen = None,
                        symbol_brush = 'r',
                        symbol_pen = 'r', 
                    ),
                ]
            ))
            
            self.registry.add_plot('Resistance', self.PlotConfig(
                x_label = 'Time', 
                x_units = 's', 
                y_label = 'Resistance', 
                y_units = 'Ω', 
                series = [
                    self.SeriesConfig(
                        x_data_name = 'ref. time', 
                        y_data_name = 'ref. resistance', 
                        label = 'Ref Res', 
                        pen = None,
                        symbol_brush = 'g',
                        symbol_pen = 'g', 
                    ),
                    self.SeriesConfig(
                        x_data_name = 'pulse time', 
                        y_data_name = 'pulse resistance', 
                        label = 'Pulse Res', 
                        pen = None,
                        symbol_brush = 'r',
                        symbol_pen = 'r', 
                    ),
                ]
            ))
            
            self.registry.add_plot('Source Voltage', self.PlotConfig(
                x_label = 'Time', 
                x_units = 's', 
                y_label = 'Source Voltage', 
                y_units = 'V', 
                series = [
                    self.SeriesConfig(
                        x_data_name = 'source time', 
                        y_data_name = 'source voltage', 
                        label = 'Source Voltage', 
                        pen = 'y',
                        symbol = None,
                        symbol_brush = 'y',
                        symbol_pen = 'y', 
                    ),
                    # self.SeriesConfig(
                    #     x_data_name = 'source time', 
                    #     y_data_name = 'source voltage', 
                    #     label = 'Source Voltage', 
                    #     pen = 'b',
                    #     symbol_brush = 'w',
                    #     symbol_pen = 'b', 
                    # ),
                ]
            ))

            self.registry.add_plot('Raman Spectra', self.PlotConfig(
                x_label = 'Raman Shift', 
                x_units = 'cm^-1',
                y_label = 'Intensity', 
                y_units = 'a.u.', 
                x_autoscale = False,
                y_autoscale = False,
                series = [
                    self.SeriesConfig(
                        x_data_name = 'raman shifts', 
                        y_data_name = 'spectra', 
                        label = 'Raman', 
                        pen = 'y',
                        symbol = None,
                        symbol_brush = 'y',
                        symbol_pen = 'y', 
                        depth=2
                    ),
                    # self.SeriesConfig(
                    #     x_data_name = 'source time', 
                    #     y_data_name = 'source voltage', 
                    #     label = 'Source Voltage', 
                    #     pen = 'b',
                    #     symbol_brush = 'w',
                    #     symbol_pen = 'b', 
                    # ),
                ]
            ))

            self.registry.add_plot('Raman Spectra (Background Removed)',self.PlotConfig(
                x_label = 'Raman Shift', 
                x_units = 'cm^-1', 
                y_label = 'Intensity', 
                y_units = 'a.u.', 
                x_autoscale = False,
                y_autoscale = False,
                series = [
                    self.SeriesConfig(
                        x_data_name = 'raman shifts', 
                        y_data_name = 'spectra_background_removed', 
                        label = 'Raman', 
                        pen = 'y',
                        symbol = None,
                        symbol_brush = 'y',
                        symbol_pen = 'y', 
                        depth=2
                    ),
                    # self.SeriesConfig(
                    #     x_data_name = 'source time', 
                    #     y_data_name = 'source voltage', 
                    #     label = 'Source Voltage', 
                    #     pen = 'b',
                    #     symbol_brush = 'w',
                    #     symbol_pen = 'b', 
                    # ),
                ]
            ))
            
            self.data_reset()

        def build_widget(self):
            """Constructs the PyQt6 widget layout."""
            self.layout = QtWidgets.QVBoxLayout()
            
            self.dataset_option = QtWidgets.QComboBox()
            self.dataset_option.addItems(self.registry.get_all_names())
            self.dataset_option.currentIndexChanged.connect(self._handleDataSetChange)
    
            self.graphics_widget = pg.GraphicsLayoutWidget(border=(100, 100, 100))
            self.plot = self.graphics_widget.addPlot(title=self.name)
            self.legend = self.plot.addLegend()
    
            self.plot_lines = []
            self.plot_setFormat()
            
            self.layout.addWidget(self.graphics_widget)
            self.layout.addWidget(self.dataset_option)
    
            self.plot_widget = QtWidgets.QWidget()
            self.plot_widget.setLayout(self.layout)
            return self.plot_widget

        def _handleDataSetChange(self):
            self.plot_setFormat()
            self.plot_update()

        def plot_setFormat(self):
            """Updates visual formatting based on the selected registry config."""
            dataset_name = self.dataset_option.currentText()
            if not dataset_name: return
            
            cfg = self.registry[dataset_name]
            
            # Flatten and remove all existing items
            for item in self.plot_lines:
                if isinstance(item, list):
                    for line in item: self.plot.removeItem(line)
                else:
                    self.plot.removeItem(item)
            
            self.plot_lines.clear()
            self.legend.clear()
    
            for s in cfg.series:
                if s.depth == 2:
                    # We don't know how many spectra there are yet, 
                    # but we prepare a list to hold them.
                    self.plot_lines.append([]) 
                else:
                    line = pg.PlotDataItem(
                        pen=s.pen, symbol=s.symbol, symbolSize=s.symbol_size, 
                        symbolBrush=s.symbol_brush, symbolPen=s.symbol_pen
                    )
                    self.plot.addItem(line)
                    self.plot_lines.append(line)
                    self.legend.addItem(line, s.label)
    
            if cfg.x_autoscale:
                self.plot.setLabel('bottom', cfg.x_label, units=cfg.x_units)
            else:
                self.plot.setLabel('bottom', cfg.x_label+f" ({cfg.x_units})")

            if cfg.y_autoscale:
                self.plot.setLabel('left', cfg.y_label, units=cfg.y_units)
            else:
                self.plot.setLabel('left', cfg.y_label+f" ({cfg.y_units})")
            
        def plot_reset(self):
            """
            Clears all currently plotted data from the screen without 
            changing the formatting or the selected dataset.
            """
            # Flatten and remove all existing items
            for item in self.plot_lines:
                if isinstance(item, list):
                    for line in item: line.setData([], [])
                else:
                    item.setData([], [])
                
        def plot_update(self):
            """Updates the PlotDataItems with actual values from the data dictionary."""
            dataset_name = self.dataset_option.currentText()
            if not dataset_name: return
            
            cfg = self.registry[dataset_name]

            #print(dataset_name)
            #print(self.registry[dataset_name])

            for line_obj, s in zip(self.plot_lines, cfg.series):
                x_val = self.data.get(s.x_data_name, [])
                y_val = self.data.get(s.y_data_name, [])

                # # Remove this
                # print(x_val)
                # print(y_val)

                if s.depth == 2:
                    spectra_list = y_val
                    
                    # Handle the list of PlotDataItems
                    current_lines = line_obj 
                    
                    while len(current_lines) > len(spectra_list):
                        line = current_lines.pop()
                        self.plot.removeItem(line)

                    for i, spec_data in enumerate(spectra_list):
                        # print(i)
                        if i >= len(current_lines):
                            # print("pass")
                            # Create new line without adding to legend
                            new_line = pg.PlotDataItem(pen='white') 
                            self.plot.addItem(new_line)
                            current_lines.append(new_line)

                        current_lines[i].setData(x_val, spec_data)
                else:
                    # Standard update for single-line series
                    line_obj.setData(x_val, y_val)

        def data_reset(self):
            """
            Initializes and resets the data in a standardized form.
            """
            self.data = {
                "ref. time" : [],
                "ref. current" : [], 
                "ref. resistance" : [],
                "ref. cycle" : [],

                # Measurement data from the pulses
                "pulse time" : [],
                "pulse current" : [],
                "pulse resistance" : [],
                "pulse cycle" : [],

                # Measurement data from the source
                "source time" : [],
                "source voltage" : [],

                # Measurement data from sequence
                "meas. end" : [],
                "meas. start" : [],
                "meas. voltage" : [],

                # Raman
                "background" : [],
                "wavelengths" : [],
                "wave numbers" : [],
                "raman shifts" : [],
                "spectra_cycle" : [],
                "spectra": [],
                "spectra_background_removed": []
                # "spectra": [ [], [] ], # [ [Cycle Num.], [Spectra] ]
                # "spectra_background_removed": [ [], [] ] # [ [Cycle Num.], [Spectra] ]
            }

            # Stores the current voltage source setpoint
            self.current_source_voltage = 0
        
        def data_append_measure(self,time,current,resistance,cycle_num,pul_or_ref):
            if pul_or_ref == 'pulse':
                self.data["pulse time"].append(time)
                self.data["pulse current"].append(current)
                self.data["pulse resistance"].append(resistance)
                self.data["pulse cycle"].append(cycle_num)
            elif pul_or_ref == 'reference':
                self.data["ref. time"].append(time)
                self.data["ref. current"].append(current)
                self.data["ref. resistance"].append(resistance)
                self.data["ref. cycle"].append(cycle_num)

        def data_append_source(self,source_time,new_source_voltage):
            self.data["source time"].append(source_time)
            self.data["source voltage"].append(self.current_source_voltage)

            self.data["source time"].append(source_time)
            self.data["source voltage"].append(new_source_voltage)

            self.current_source_voltage = new_source_voltage

        def data_append_read(self, meas_start_time,meas_end_time, meas_source_volts):
            # Data about the measurement
            self.data["meas. end"].append(meas_start_time)
            self.data["meas. start"].append(meas_end_time)
            self.data["meas. voltage"].append(meas_source_volts)

        def data_append_spectra(self,cycle_number,spectra,spectra_bkgnd_rmv):
            self.data["spectra_cycle"].append(cycle_number)
            self.data["spectra"].append(spectra)
            self.data["spectra_background_removed"].append(spectra_bkgnd_rmv)

    def setup_figure(self):
        """
        Runs once during app initialization and is responsible
        for creating a QtWidgets.QWidget self.ui.  
        """
        # ----- Measurement Control Board (cb) -----
        cb_layout = QtWidgets.QHBoxLayout()

        # Pulse and Reference settings layout (pul)
        volt_layout=QtWidgets.QVBoxLayout()
        volt_layout.addWidget(
            self.settings.New_UI(
                include = ("Pulse DC Voltage",
                           "Pulse Width",
                           "Pulse Meas. Delay"),
                title="Pulse Settings",
            )
        )

        volt_layout.addWidget(
            self.settings.New_UI(
                include = ("Reference DC Voltage",
                           "Reference Width",
                           "Reference Meas. Delay"),
                title="Reference Settings",
            )
        )

        cb_layout.addLayout(volt_layout)

        # Measurement Settings Layout
        mset_layout=QtWidgets.QVBoxLayout()
        mset_layout.addWidget(
            self.settings.New_UI(
                include = ("Continuous","Number of Cycles",
                            "Meas. Range", "NPLC"),
                title="Collection Settings"
            )
        )

        # TODO: Add function to black out the stop time when not specified

        cb_layout.addLayout(mset_layout)

        # Run Setting Layout
        run_layout=QtWidgets.QVBoxLayout()
        run_layout.addWidget(
            self.settings.New_UI(
                include = ("progress","save_h5"),
            )
        )
        run_layout.addWidget(self.new_start_stop_button())
        
        cb_layout.addLayout(run_layout)

        
        header_widget = QtWidgets.QWidget()
        header_layout = QtWidgets.QVBoxLayout(header_widget)
        header_layout.addLayout(cb_layout)

        # ----- Plotting Widget -----
        self.graphics_widget = self.dm.build_widget()

        # ScopeFoundry assumes .ui is the main widget:
        self.ui = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.ui.addWidget(header_widget)
        self.ui.addWidget(self.graphics_widget)
    
    def update_display(self):
        """
        Updates the plot. This is an inherited function from the 
        Measurement class.
        """
        self.dm.plot_update()

    def pre_run(self):
        """
        Runs right before the measurement starts. This is an inherited function 
        from the Measurement class.
        """
        # Reset the data
        self.dm.data_reset()

        # Clear the plot
        self.dm.plot_reset()

        # Reference the Required Scope Foundry Hardware Class (HW)
        self.keithley  = self.app.hardware["sourcemeter2400"]

        # Check to make sure that the Keithley is connected
        if not self.keithley.settings["connected"]:
            raise RuntimeError("Keithley Sourcemeter not connected.")


        # Reference the Keithley Low-Level Communications Device Class (Dev)
        self.dev = self.keithley.dev

        # Check if the Keithley is in debug mode
        self.debug = self.dev.debug

        if not self.debug:
            # Picam
            try:
                self.picam = self.app.hardware['picam']
                self.picam_readout = self.app.measurements['picam_readout']
                self.picam_readout.interrupt()
                # Make sure hw settings are synced.
                self.picam.commit_parameters()
            except:
                raise RuntimeError("Could not connect to picam.")

            # White light flip
            try:
                self.white_light_flip = self.app.hardware['white_light_flip']
            except:
                raise RuntimeError("Could not connect to white light flip.")

            # # Laser shutter
            # try:
            #     laser_in_shutter = self.app.hardware['laser_in_shutter']
            #     laser_in_shutter.settings['named_position'] = 'CLOSED'
            # except:
            #     raise RuntimeError("Could not connect to shutter.")

        # ----- Prepare the Keithley -----
        # Reference the measurement settings
        s = self.settings

        # Set the source and sense modes
        if self.debug:
            print('\nSET SOURCE/SENSE')

        self.keithley.start_measurement(
            source = 'voltage',
            sense  = 'current',
            NPLC = self.settings['NPLC'],
            source_range = 'Auto',
            sense_range = self.settings['Meas. Range'],
        )

        # Set the current source voltage
        self.current_source_voltage = 0

        # Set voltage setpoint to the DC Voltage
        if self.debug:
            print('\nPREPARE IT MEASUREMENT')
    
    def run(self):
        """
        Runs when the measurement starts. Executes in a separate thread from the GUI.
        It should not update the graphical interface directly and should focus only
        on data acquisition.
        """
        # Reference the measurement settings
        s = self.settings

        # Prepare the measurement
        if self.debug:
            print("\nRunning Measurement Loop")
            print("------------------------\n")

        self.timer = self.Timer()        

        def measure_current(pulse_or_reference, cycle_num,
                            output_duration=False):
            """
            Handles the electrical measurement.
            """
            # Measure the current and duration of the measurement.
            meas_start = self.timer.time()
            (voltage, current, current_err, resistance) = self.keithley.read_current()
            meas_end = self.timer.time()

            # TODO: Add short circuit detection here.

            meas_duration  = (meas_end - meas_start)
            meas_time = (meas_end + meas_start) / 2

            self.dm.data_append_measure(
                meas_time,
                current,
                resistance,
                cycle_num,
                pulse_or_reference
            )

            # Check to make sure the device hasn't broken
            if self.keithley.is_short_circuit(current):
                self.interrupt_measurement_called = True
                print("Short circuited detected.")

            # Return the measurement duration if necessary
            if output_duration:
                return meas_duration
            else:
                return

        def laser_open(on_off:bool):
            """Switch the laser on and off."""
            if on_off:
                if not self.debug:
                    self.white_light_flip.settings['named_position'] = 'laser'
                else:
                    print("Open laser.")
            else:
                if not self.debug:
                    self.white_light_flip.settings['named_position'] = 'white_light'
                else:
                    print("Close laser.")
                
            # Delay to allow time for flipping to finish
            time.sleep(2)
            

        def calibrate_electrical_measurement(num_calibration_pts=5): 
            """
            Takes the first electrical measurements and then  calculates the
            approximate duration of each measurement. This will determine the
            number of measurements during each pulse and reference step.
            """
            # Calibrate the auto range by taking a measurement and tossing it
            if s['Meas. Range'] == 'Auto':
                self.keithley.read_current()

            # Measurement data
            durations = []
            for N in range(num_calibration_pts):
                durations.append(
                    measure_current(
                        'reference',
                        int(0),
                        output_duration=True)
                )

            # Calculate the average duration of each measurement
            durations = np.array(durations)
            avg_meas_time = np.average(durations)
            std_meas_time = np.std(durations)

            # Calculate the pulse and reference expiration times to end cycles
            def calc_step_expire_time(pulse_width, meas_delay):
                step_expire_time = pulse_width - avg_meas_time - meas_delay
                return step_expire_time

            self.pulse_expire_time = calc_step_expire_time(
                s["Pulse Width"],
                s["Pulse Meas. Delay"]
            )

            self.reference_expire_time = calc_step_expire_time(
                s["Reference Width"],
                s["Reference Meas. Delay"]
            )

            self.dm.data_append_source(
                self.timer.time(),
                s["Reference DC Voltage"]
            )
            return

        def measure_raman(cycle_number):
            """Measure the raman"""
            # Set the voltage to zero
            self.keithley.write_voltage(0)

            self.dm.data_append_source(
                self.timer.time(),
                0
            )

            # Unblock the laser
            laser_open(True)

            # Collect the Raman Spectrum
            if self.debug:
                print("Measure Raman Spectra")

                # Generate Lorentzian test data if in debug mode
                fwhm = 75 # Full width, half max
                x0 = 350 # Center
                g = fwhm / 2.0 # Gamma
                A = cycle_number # Amplitude
                spectrum = (
                    A * (g**2 / ((self.raman_shifts - x0)**2 + g**2))
                    + self.background
                )

            else:                          
                # Raman Measurement
                self.picam_readout.settings['continuous'] = False
                self.start_nested_measure_and_wait(self.picam_readout, polling_time=0.1)

                spectrum = self.picam_readout.spectrum

            # Block the laser
            laser_open(False)

            spectrum_bkgnd_rmv = spectrum - self.background

            # Store the data in the data manager
            self.dm.data_append_spectra(cycle_number, spectrum, spectrum_bkgnd_rmv)
            return

        
        def step_voltage_routine(pulse_or_reference,cycle_num):
            """
            Runs the sourcemeter routine for one step (pulse or reference) of 
            the pulsing cycle. The appropriate voltage setpoints are written
            and the current is measured continuously, with specified delay
            between each, until there is not enough time to take another
            measurement (expire_time). At that point, the step continues until
            the step width is met. 
            """
            # Set the voltage for the current step
            if pulse_or_reference == 'pulse':
                self.keithley.write_voltage(s['Pulse DC Voltage'])
                expire_time = self.pulse_expire_time
                width = s['Pulse Width']

                self.dm.data_append_source(
                    self.timer.time(),
                    s["Pulse DC Voltage"]
                )

                if self.debug:
                    print("PULSE ROUTINE")

            elif pulse_or_reference == 'reference':
                self.keithley.write_voltage(s['Reference DC Voltage'])
                expire_time = self.reference_expire_time
                width = s['Reference Width']

                self.dm.data_append_source(
                    self.timer.time(),
                    s["Reference DC Voltage"]
                )

                if self.debug:
                    print("REFERENCE ROUTINE")

            # Begin the timer for the current cycle
            end_step = False
            step_timer = self.Timer()
            step_timer.start()

            while not end_step:
                # Measure the current and record the data
                measure_current(pulse_or_reference, cycle_num)

                # Check if there is time to run another measurement
                current_time = step_timer.time()
                if current_time > expire_time:
                    # Set flag to end the current step
                    end_step = True

                    # Hold the voltage without measuring for the remaining time
                    if width - current_time > 0:
                        time.sleep(width - current_time)

                self.sig_worker.update_plot.emit()

                # Check if end measurement was called during the pulse step
                if (self.interrupt_measurement_called and 
                    pulse_or_reference == 'pulse'):
                    end_step = True
            
            return

        # ---------------------------------------------------------------------
        # Run the measurement loop
        # ---------------------------------------------------------------------
        cycle_num = 0

        while not self.interrupt_measurement_called:
            if self.debug:
                print(f"\nCycle #: {cycle_num}")

            if not s["Continuous"]:
                # Update the progress bar
                self.sig_worker.update_progress.emit(
                    (cycle_num) * 100.0 / s["Number of Cycles"]
                )
            
            if cycle_num == 0:
                # ----- Measure the Background Raman -----
                #   Measure the Raman while the laser is blocked.
                # Block the laser
                laser_open(False)

                # Collect the background spectrum
                if self.debug:
                    # Generate test data if in debug mode
                    if cycle_num == 0:
                        self.raman_shifts = np.linspace(1,1000,500)
                        self.wls = self.raman_shifts
                        self.wave_numbers = 1 / self.raman_shifts

                        # Simulate linear background
                        self.background = 0.001 * self.raman_shifts
                else:                   
                    # Measure the raman
                    self.picam_readout.settings['continuous'] = False
                    self.start_nested_measure_and_wait(
                        self.picam_readout,
                        polling_time=0.1
                    )

                    self.wls = np.array(self.picam_readout.wls)
                    self.wave_numbers = np.array(self.picam_readout.wave_numbers)
                    self.raman_shifts = np.array(self.picam_readout.raman_shifts)

                    self.background = self.picam_readout.spectrum

                # Store the data in the Data Manager
                self.dm.data['wavelengths']  = list(self.wls)
                self.dm.data['wave numbers'] = list(self.wave_numbers)
                self.dm.data['raman shifts'] = list(self.raman_shifts)
                self.dm.data['background']   = list(self.background)

                time.sleep(1)

                # ----- Turn on the Sourcemeter & Calibrate -----
                # Begin timing the measurement
                self.timer.start()
                time.sleep(0.2) # Allow voltage to stabilize before measurement

                # Turn on the voltage output on the sourcemeter
                self.keithley.write_voltage(0)
                self.keithley.write_output('ON')
                time.sleep(0.2)

                # Record the reference
                self.keithley.write_voltage(s["Reference DC Voltage"])
                self.dm.data_append_source(
                    self.timer.time(),
                    s["Reference DC Voltage"]
                )

                # Calibrate the timing of the pulse measurements
                calibrate_electrical_measurement()

                # Take the first raman measurement of the sample
                measure_raman(cycle_num)

                # Continue to the next cycle
                cycle_num = cycle_num + 1
                continue

            # Pulse sequence
            step_voltage_routine('pulse',cycle_num)
            step_voltage_routine('reference',cycle_num)

            time.sleep(1)
            measure_raman(cycle_num)

            self.sig_worker.update_plot.emit() 

            # End the measurement once the stop time is reached
            if not s["Continuous"]:
                if cycle_num >= s["Number of Cycles"]:
                    self.interrupt_measurement_called = True

            cycle_num = cycle_num + 1

        # End the measurement
        self.keithley.write_output('OFF')

        # Save the data as each measurement is completed
        if self.settings["save_h5"]:
            # self.save_h5(data=self.dm.data)
            try:
                self.save_h5(data=self.dm.data)
            except:
                # If a .h5 fails to save, save the data as a .json file
                from datetime import datetime
                import json
                timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
                filename = f"{timestamp}_{self.name}.json"
                filepath = self.dataset_metadata.h5_file_path.parent / filename

                with open(filepath, "w") as f:
                    json.dump(self.dm.data, f, indent=4)

                print("\nWARNING!: h5 failed to save. Saved as .json.\n")

    def post_run(self):
        # Try to change the setpoint to zero and turn off the Keithley
        try:
            self.keithley.write_voltage(0)
            self.keithley.write_output('OFF')
        except:
            pass

