"""
Created on Aug 07, 2026

@author: 
"""

import pyqtgraph as pg
from qtpy import QtCore, QtWidgets

from ScopeFoundry import Measurement, h5_io

import numpy as np
import time

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

class DataManager():
    """
    Custom class to the manage the data and plotting
    """
    def __init__(self, name):
        self.name = name

    def build_widget(self):
        """
        Creates the plot widget
        """
        # Create the main layout for the plot area
        self.layout = QtWidgets.QVBoxLayout()

        # Create a dropdown box to select which data set to plot
        self.dataset_widget = QtWidgets.QComboBox()
        self.dataset_widget.addItem('Current')
        self.dataset_widget.addItem('Resistance (V/I)')
        self.dataset_widget.currentIndexChanged.connect(self._handleDataSetChange)

        # Create the graphics widget for the plot
        self.graphics_widget = pg.GraphicsLayoutWidget(border=(100, 100, 100))
        self.plot = self.graphics_widget.addPlot(title=self.name)
        self.plot_lines = {}
        self.plot_lines["data"] = self.plot.plot(
            pen="g",
            symbol = "o",
            symbolBrush="g",
            symbolSize=8,
            symbolPen="g"
        )

        # Set the labels
        self.plot_setLabel()
        
        # Add the widgets to the main layout
        self.layout.addWidget(self.graphics_widget)
        self.layout.addWidget(self.dataset_widget)

        self.plot_widget = QtWidgets.QWidget()
        self.plot_widget.setLayout(self.layout)

        return self.plot_widget

    def _handleDataSetChange(self):
        self.plot_setLabel()
        self.plot_update()

    def plot_setLabel(self):
        """
        Set the axis labels depending on the dataset selected in the dataset
        QComboBox.
        """
        x_label = 'Time'
        x_units='s'
        
        if self.dataset_widget.currentText() == 'Current':
            y_label = 'Current'
            y_units = 'A'
            color = 'g'
        elif self.dataset_widget.currentText() == 'Resistance (V/I)':
            y_label = 'Resistance'
            y_units = 'Ω'
            color = 'r'

        # Update the formatting
        self.plot.setLabel('bottom', x_label, units=x_units)
        self.plot.setLabel('left', y_label, units=y_units)
        self.plot_lines["data"].pen=color
        self.plot_lines["data"].symbolBrush = color
        self.plot_lines["data"].symbolPen = color

        self.plot.update() 
        

    def plot_reset(self):
        if "data" in self.plot_lines:
            self.plot_lines["data"].setData([], [])

    def plot_update(self):
        if self.dataset_widget.currentText() == 'Current':
            self.plot_lines['data'].setData(self.data['t'], self.data['I'])
        elif self.dataset_widget.currentText() == 'Resistance (V/I)':
            self.plot_lines['data'].setData(self.data['t'], self.data['R'])

    def data_reset(self):
        self.data = {"t":[], "I":[], "R":[]}

    def data_append(self,time,current,resistance):
        self.data["t"].append(time)
        self.data["I"].append(current)
        self.data["R"].append(resistance)
        

class DCTimeEvolution(Measurement):

    name = "dc_time_evolution_readout"

    def setup(self):
        """
        Runs once during app initialization.
        This is where you define your settings, 
        and set up data structures.
        """
        s = self.settings
        
        # Save h5 file
        s.New("save_h5", 
                bool, 
                initial=False)

        # DC Voltage
        s.New(
            "DC Voltage", float, initial=0.5, unit='V',si=True,
            description= ("Constant DC voltage.")
        )

        # Measurement Period
        s.New(
            "Time Step", float, initial=0.5, unit='s',si=True,
            description= ("Time in between measurements.")
        )

        # Continuous
        s.New(
            "Continuous", bool, initial=True,
            description=("Enable continuous measuring without stoppage time.")
        )

        # Number of Power Line Cycles (NPLC)
        s.New(
            "NPLC", float, initial=1, vmin=0.01, vmax=10,
            description=("Number of power line cycles (0.01-10)."
                         "Proportional to the integration time.")
        )

        # Duration
        s.New(
            "Stop Time", float, initial=0.0, unit='s',si=True,
            description= ("Duration of the measurement before stopping.")
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
        self.dm = DataManager(self.name)
        
        # Initialize the signal worker
        self.sig_worker = SignalWorker()

    
    def setup_figure(self):
        """
        Runs once during app initialization and is responsible
        for creating a QtWidgets.QWidget self.ui.
        """
        # ----- Measurement Control Board (cb)
        cb_layout = QtWidgets.QHBoxLayout()

        # Voltage Layout (volt)
        volt_layout=QtWidgets.QVBoxLayout()
        volt_layout.addWidget(
            self.settings.New_UI(
                include = ("DC Voltage",),
                title="Voltage",
            )
        )

        cb_layout.addLayout(volt_layout)

        # Measurement Settings Layout
        mset_layout=QtWidgets.QVBoxLayout()
        mset_layout.addWidget(
            self.settings.New_UI(
                include = ("Time Step","Continuous","Stop Time",
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

        # Reference the Keithleley Scope Foundry Hardware Class (HW)
        self.hw  = self.app.hardware["sourcemeter2400"]

        # Refer the Keithley Low-Level Communications Device Class (Dev)
        self.dev = self.hw.dev
        

        # Connect the signals to display update functions and progress update
        self.sig_worker.update_plot.connect(
            self.update_display, 
            QtCore.Qt.QueuedConnection
        )
        
        self.sig_worker.update_progress.connect(
            self.set_progress,
            QtCore.Qt.QueuedConnection
        )

        self.hw.start_measurement(
            source = 'voltage',
            sense  = 'current',
            NPLC = self.settings['NPLC'],
            source_range = 'Auto',
            sense_range = self.settings['Meas. Range'],
        )
    
    def run(self):
        """
        Runs when the measurement starts. Executes in a separate thread from the GUI.
        It should not update the graphical interface directly and should focus only
        on data acquisition.
        """
        # Reference the measurement settings
        s = self.settings

        # Check debug boolean
        debug = self.dev.debug

        # Prepare the measurement
        if debug:
            print("\nRunning IT Measurement")
            print("------------------------\n")

        # Set the source and sense modes
        if debug:
            print('\nSET SOURCE/SENSE')

        # Set voltage setpoint to the DC Voltage
        if debug:
            print('\nPREPARE IT MEASUREMENT')
        self.hw.write_voltage(s["DC Voltage"])
        self.hw.write_output('ON')

        # Run the measurement loop
        start_time = time.time()
        time.sleep(0.25) # Allow voltage to stabilize before measurement

        # Calibrate auto range
        if s['Meas. Range'] == 'Auto':
            self.hw.read_current()

        while not self.interrupt_measurement_called:
            # Read measured values
            (voltage, current, current_err, resistance) = self.hw.read_current()
            curr_time = time.time() - start_time

            # Store the data
            self.dm.data_append(curr_time, current, resistance)

            # Signal to update the data plot
            self.sig_worker.update_plot.emit()

            # Print the readout
            if debug:
                print('Readout:')
                print(f'Time: {curr_time:.2f} V, Current: {current:.2e} A')

            # Wait to take the next measurement
            time.sleep(s['Time Step'])

            # End the measurement once the stop time is reached
            if not s["Continuous"]:
                if curr_time > s["Stop Time"]:
                    self.interrupt_measurement_called = True

        # End the measurement
        self.hw.write_output('OFF')

        # Save the data as each measurement is completed
        if self.settings["save_h5"]:
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
        # Try to change the setpoint to zero
        try:
            self.hw.write_voltage(0)
        except:
            pass

        # Try to turn off the Keitheley
        try:
            self.hw.write_output('OFF')
        except:
            pass