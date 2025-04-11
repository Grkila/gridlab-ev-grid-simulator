import stages
import mapping
import ppscenarios
import easygui
import utils
"""
This module provides the basic graphic interface to call
the modules that perform the tool's required functions.

The available options are:
Stages: calls the module that orchestrates the multi-stage algorithm to import 
    the open data and generate the power grid model.
pandapower: presents an interface to run scenarios to test the generated
    power grid model with pandapower. All stages must be run first to generate
    the model before using this option.
Maps: presents an interface to generate interactive maps from various
    stages of the process.
"""

if __name__ == "__main__":
    """
    data.pkl: the pickle file that contains all the data from previous runs of the program
    last_saved: integer representing the last stage that was sucessfully run 
    """
    data = utils.data_un('data.pkl')
    if data == {}:
        data = {'last_saved': 0}
    choice = easygui.buttonbox(
        title='Choose Functionality',
        msg='Select which module to run',
        choices=['Stages', 'pandapower', 'Maps']
    )

    if choice == 'Stages':
        stages.run_stages(data, None)
    elif choice == 'pandapower':
        ppscenarios.run_scenarios(data)
    elif choice == 'Maps':
        mapping.create_maps(data)