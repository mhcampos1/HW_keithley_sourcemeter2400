'''
Created on Jul 16, 2026

@author: Misael Campos
'''

from ScopeFoundry.base_app import BaseMicroscopeApp


class TestApp(BaseMicroscopeApp):

    name = "sourcemeter2400_test_app"

    def setup(self):
        
        from ScopeFoundryHW.keithley_sourcemeter2400 import Sourcemeter2400HW, Sourcemeter2400Readout
        self.add_hardware(Sourcemeter2400HW(self))
        self.add_measurement(Sourcemeter2400Readout(self))



if __name__ == '__main__':
    import sys
    app = TestApp(sys.argv)
    sys.exit(app.exec_())
