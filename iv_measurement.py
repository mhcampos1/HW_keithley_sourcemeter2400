"""
Created on Jul 23, 2026

@author: 
"""

import pyqtgraph as pg
from qtpy import QtCore, QtWidgets

from ScopeFoundry import Measurement, h5_io
# from ScopeFoundryHW.keithley_sourcemeter2400.sourcemeter2400_dev import Sourcemeter2400Dev

import numpy as np
import time

class IVmeasurement(Measurement):

    name = "iv_measurement_readout"

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
        Custom class to manage the data acquisition and plotting
        for a specific measurement.
        """
        def __init__(self, name: str):
            """
            Initializes the DataManager with a unique name for identification.
            """
            self.name = name
            self.data = {"voltage": [], "current": [], "avg_resistance":float}  # Initialize with the expected data structure
            self.plot_lines = {}

        def plot_build(self) -> pg.GraphicsLayoutWidget:
            """
            Builds the necessary PyQtGraph widgets (Plot, Layout) for visualization.
            This method should return the main widget container.
            """
            # 1. Create the main layout widget
            self.graphics_widget = pg.GraphicsLayoutWidget(border=(100, 100, 100))
            
            # 2. Add the primary plot
            self.plot = self.graphics_widget.addPlot(title=self.name)
            
            # 3. Initialize plot line configurations
            color='g'
            self.plot_lines["IV"] = self.plot.plot(
                pen=color,
                symbol="o",
                symbolSize=8,
                symbolBrush=color,
                symbolPen=color
            )
            
            # 4. Set axis labels
            self.plot.setLabel('bottom', 'Voltage', units='V')
            self.plot.setLabel('left', 'Current', units='A')

            return self.graphics_widget

        def reset(self):
            """
            Resets the data and plot.
            """
            self.data_reset()
            self.plot_reset()

        def data_reset(self):
            """
            Resets the internal data storage to empty lists.
            """
            self.data = {"voltage": [], "current": []}

        def data_append(self, voltage: float, current: float):
            """
            Appends a new data point to the internal data structures.
            """
            self.data["voltage"].append(voltage)
            self.data["current"].append(current)

        def plot_reset(self):
            """
            Clears the data displayed on the plot by resetting the data for all lines.
            """
            if "IV" in self.plot_lines:
                self.plot_lines["IV"].setData([], [])

        def plot_update(self):
            """
            Updates the visualization by feeding the current data from self.data
            to the corresponding plot line object.
            """
            if "IV" in self.plot_lines:
                line = self.plot_lines["IV"]
                line.setData(self.data["voltage"], self.data["current"])

        def calc_avg_resistance(self):
            """
            """
            if len(self.data["voltage"]):
                R_avg, b = np.polyfit(np.array(self.data["current"]),np.array(self.data["voltage"]),1)

            print(f"Avg. Resistance: {R_avg:.3e} Ω")

    def setup(self):
        """
        Runs once during app initialization. This is where you define your 
        settings, and set up data structures. This is an inherited function.
        """
        s = self.settings

        # Save h5 file
        s.New("save_h5", 
              bool, 
              initial=False)

        # Voltage sweeping range
        self.voltage_range = s.New_Range(
            "Voltage Range", initials = [-0.1, 0.1, 0.02], unit = "V", si=True, 
            vmin = -20, vmax = 20,
            description = "Voltage sweep range."
        )

        # Voltage Stabilization Time
        s.New(
            "Stabilization Time", float, initial=0.2, unit='s',si=True,
            description= ("Time delay before taking a measurement after a new"
                          "voltage is applied.")
        )

        # Voltage Stabilization Time
        s.New(
            "Cooldown Time", float, initial=0.0, unit='s',si=True,
            description= ("Off-time in between voltage applications and "
                          "measurements.")
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

    def setup_figure(self):
        """
        Runs once during app initialization and is responsible
        for creating a QtWidgets.QWidget self.ui. This is an inherited class
        from the Measurement class.
        """

        # ----- Measurement Control Board (cb)
        cb_layout = QtWidgets.QHBoxLayout()
        
        # Voltage range (vrng) Layout
        vrng_layout=QtWidgets.QVBoxLayout()
        vrng_layout.addWidget(
            self.settings.New_UI(
                include = ("Voltage Range_min","Voltage Range_max",
                           "Voltage Range_step", "Voltage Range_num"),
                title="Voltage Sweep",
            )
        )

        cb_layout.addLayout(vrng_layout)

        # Measurement Settings Layout
        mset_layout=QtWidgets.QVBoxLayout()
        mset_layout.addWidget(
            self.settings.New_UI(
                include = ("Stabilization Time","Cooldown Time",
                            "Meas. Range", "NPLC"),
                title="Collection Settings"
            )
        )

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
        self.graphics_widget = self.dm.plot_build()

        # ScopeFoundry assumes .ui is the main widget:
        self.ui = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.ui.addWidget(header_widget)
        self.ui.addWidget(self.graphics_widget)

    def update_display(self):
        """
        Delegates plot update to the DataManager. This is an inherited
        function from the Measurement class.
        """
        self.dm.plot_update()

    def pre_run(self):
        """
        Runs right before the measurement starts. This is an inherited function
        from the Measurement class.
        """
        # Reset the data and plot using the DataManager
        self.dm.reset()

        # Reference the Keithleley Scope Foundry Hardware Class (HW)
        self.hw  = self.app.hardware["sourcemeter2400"]

        # Refer the Keithleley Low-Level Communications Device Class (Dev)
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

        # Check debug boolean
        self.debug = self.dev.debug

        # Prepare the measurement
        if self.debug:
            print("\nRunning IV Measurement")
            print("------------------------\n")

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

        # Turn on the output
        self.hw.write_output("ON")

        # Sweep the voltage setpoints and measure the current
        N = len(self.voltage_range.sweep_array)
        for i, V in enumerate(self.voltage_range.sweep_array):
            # Check to make sure that interruption not called
            if self.interrupt_measurement_called:
                break

            if self.debug:
                print(f'\nIV DATA POINT {i+1}')

            # Set the voltage
            self.hw.write_voltage(V)

            # Wait for the voltage to stabilize
            time.sleep(s['Stabilization Time'])

            # Read measured values
            (voltage, current, current_err, resistance) = self.hw.read_current()

            # Store the data using the DataManager
            self.dm.data_append(voltage, current)

            # Signal to update the data plot
            self.sig_worker.update_plot.emit()

            # Signal to update the progress bar
            self.sig_worker.update_progress.emit(i * 100.0 / N)

            # Print the readout
            if self.debug:
                print('Readout:')
                print(f'Voltage: {voltage:.2e} V, Current: {current:.2e} A')

            # Cooldown if Specified
            if s['Cooldown Time'] != 0:
                if self.debug:
                    print(f'\nCOOLDOWN {i+1}')

                # Set voltage to zero
                self.hw.write_voltage(0)

                # Wait for cooldown time
                time.sleep(s['Cooldown Time'])

        # End the measurement
        self.hw.write_output('OFF')

        # Calculate the average resistance
        self.dm.calc_avg_resistance()

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
        """
        Inherited function that runs after the measurement run is interrupted 
        or is completed.
        """
        # In case of interruption try to turn off the output

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