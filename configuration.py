
import os
import ConfigParser

class Dropbox(object):

    section='DROPBOX'

    def __init__(self, filename):
        config = self.config = ConfigParser.SafeConfigParser()
        config.read(filename)

        section = self.section

        if not config.has_section(section):
            raise Exception("Dropbox config does not have %s section" % section)

        self.APP_KEY = config.get(section, 'APP_KEY')
        self.APP_SECRET = config.get(section, 'APP_SECRET')
        self.ACCESS_TYPE = config.get(section, 'ACCESS_TYPE')

class Configuration(object):


    def __init__(self):
        mypath = os.path.dirname(__file__)
        config_path = os.path.join(mypath, 'dropboxapp.ini')
        self.dropbox = Dropbox(config_path)


configuration = Configuration()
