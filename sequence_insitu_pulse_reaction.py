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

class SequenceInsituPulseReaction(Measurement):

    name = "sequence_insitu_pulse_reaction"

    class SignalWorker(QtCore.QObject):
        """
        Class to handle Qt.Signals. 
        """
        # Signal to update the progess bar
        update_progress = QtCore.Signal(float)

        def __init__(self, parent=None):
            super().__init__(parent)

    def setup(self):
        """
        Runs once during app initialization. This is where you define your 
        settings, and set up data structures. This is an inherited function.
        """
        s = self.settings

        # Voltage sweeping range
        self.voltage_range = s.New_Range(
            "voltage_range", initials = [0.5, 3, 0.1], unit = "V", si=True, 
            vmin = -20, vmax = 20,
            description = "Voltage sweep range."
        )
        
        # Initialize the signal worker
        self.sig_worker = self.SignalWorker()

    def setup_figure(self):
        """
        Runs once during app initialization and is responsible
        for creating a QtWidgets.QWidget self.ui. This is an inherited class
        from the Measurement class.
        """

        # ----- Measurement Control Board (cb)
        cb_layout = QtWidgets.QVBoxLayout()
        
        # Voltage range (vrng) Layout
        vrng_layout=QtWidgets.QVBoxLayout()
        vrng_layout.addWidget(
            self.settings.New_UI(
                include = ("voltage_range_min","voltage_range_max",
                           "voltage_range_step", "voltage_range_num"),
                title="Voltage Sweep",
            )
        )

        cb_layout.addLayout(vrng_layout)

        # Run Setting Layout
        run_layout=QtWidgets.QVBoxLayout()
        run_layout.addWidget(
            self.settings.New_UI(
                include = ("progress",),
            )
        )
        run_layout.addWidget(self.new_start_stop_button())
        
        cb_layout.addLayout(run_layout)

        header_widget = QtWidgets.QWidget()
        header_layout = QtWidgets.QVBoxLayout(header_widget)
        header_layout.addLayout(cb_layout)

        # ScopeFoundry assumes .ui is the main widget:
        self.ui = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.ui.addWidget(header_widget)

    def pre_run(self):
        """
        Runs right before the measurement starts. This is an inherited function
        from the Measurement class.
        """
        # Connect the signals to display update functions and progress update        
        self.sig_worker.update_progress.connect(
            self.set_progress,
            QtCore.Qt.QueuedConnection
        )

        # Check debug boolean
        self.debug = self.app.hardware["sourcemeter2400"].dev.debug

        self.insitu_pulse_reaction = self.app.measurements[
            'insitu_pulse_reaction_readout'
        ]

        try:
            self.nd_wheel = self.app.hardware["nd_wheel"]
        except (KeyError, ConnectionError, OSError) as exc:
            raise RuntimeError(
                "ND wheel is unavailable, disconnected, or could not be read."
            ) from exc
    
    def run(self):
        """
        Runs when the measurement starts. Executes in a separate thread from the GUI.
        It should not update the graphical interface directly and should focus only
        on data acquisition.
        """

        print("\n" + "-*" * 40)
        print("\nBEGINNING SEQUENTIAL INSITU REACTION")
        print("\n" + "-*" * 40)

        # Set progress to begin with
        self.sig_worker.update_progress.emit(0.1)


        # Make sure the data will save
        self.insitu_pulse_reaction.settings["save_h5"] = True

        starting_filter_position = self.nd_wheel.settings["named_position"]
        print(f"Sequence Start: {starting_filter_position}")

        if starting_filter_position == "F_CLOSED":
            raise RuntimeError("ND wheel is closed and blocking the laser.")

        # Sweep the voltage setpoints and measure the current
        N = len(self.voltage_range.sweep_array)
        for i, V in enumerate(self.voltage_range.sweep_array):
            print(f"Experiment # {i+1}: {V:.2e} V")
            print(f"\nBefore Move in Sequence: {self.nd_wheel.settings["named_position"]}, Target:{starting_filter_position}")
            self.nd_wheel.settings["named_position"] = starting_filter_position
            time.sleep(3)
            print(f"After Move in Sequence: {self.nd_wheel.settings["named_position"]}, Target:{starting_filter_position}\n")
            self.insitu_pulse_reaction.settings["pulse_voltage"] = V

            # Begin the measurement and record if it is completed successfully
            measurement_success = self.start_nested_measure_and_wait(
                self.insitu_pulse_reaction, nested_interrupt = False
            )

            # Signal to update the progress bar
            self.sig_worker.update_progress.emit((i+1) * 100.0 / N)

            # If the last measurement was interrupted or unsuccessful end
            if not measurement_success:
                break

    def post_run(self):
        """
        Inherited function that runs after the measurement run is interrupted 
        or is completed.
        """
        print("\n" + "-*" * 40)
        print("\nSequenceInsituPulseReaction Complete.")
        print("\n" + "-*" * 40)

        try:
            self.nd_wheel.settings["named_position"] = "F_CLOSED"
            time.sleep(3)
        except:
            pass
        
        # In case of interruption try to turn off the output
