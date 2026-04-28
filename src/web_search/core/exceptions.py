class WebSearchException(Exception):
    pass


class ProviderNotFoundException(WebSearchException):
    pass


class ConfigurationException(WebSearchException):
    pass
