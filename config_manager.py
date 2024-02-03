import configparser

class ConfigManager:
    def __init__(self, config_file):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)

    def get_settings(self):
        return self.config['Settings']

    def get_trigger_filters(self):
        trigger_filters = []
        section = self.config['TriggerFilters']
        for key in section:
            trigger_filters.append({"description": section[key]})
        return trigger_filters
    
    def get_graph_settings(self):
        return self.config['GraphSettings']