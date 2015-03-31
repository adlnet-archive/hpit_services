import os
import nose

from hpit.management.settings_manager import SettingsManager
settings = SettingsManager.get_server_settings()

class Command:
    description = "Unit Test the code."
    arguments = ['--test-path']
    
    def __init__(self, manager, parser):
        self.manager = manager
    
    def run(self, arguments, configuration):
        
        env = os.environ['HPIT_ENV'] if 'HPIT_ENV' in os.environ else None
        if not env or 'test' not in env:
            answer = input("WARNING: 'test' is not found in HPIT_ENV ({}). Continue anyway? [y/n] ".format(env))
            if answer.lower() == "n":
                return
        
        self.configuration = configuration

        test_path = os.path.join(settings.PROJECT_DIR, 'tests')

        if arguments.test_path:
            test_path = arguments.test_path

        nose.main(argv=['-w', test_path, '--verbose' , '--nologcapture', "-x"])
