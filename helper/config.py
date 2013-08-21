"""
Responsible for reading in configuration files, validating the proper
format and providing sane defaults for parts that don't have any.

"""
import logging
from os import path
import platform
import yaml

(major, minor, rev) = platform.python_version_tuple()
if float('%s.%s' % (major, minor)) < 2.7:
    from logutils import dictconfig as logging_config
else:
    from logging import config as logging_config
LOGGER = logging.getLogger(__name__)


class Config(object):
    """The Config object holds the current state of the configuration for an
    application. If no configuration file is provided, it will used a set of
    defaults with very basic behavior for logging and daemonization.

    """
    APPLICATION = {'wake_interval': 60}
    DAEMON = {'user': None,
              'group': None,
              'pidfile': None,
              'prevent_core': True}
    LOGGING_FORMAT = ('%(levelname) -10s %(asctime)s %(process)-6d '
                      '%(processName) -15s %(threadName)-10s %(name) -25s '
                      '%(funcName) -25s L%(lineno)-6d: %(message)s')
    LOGGING = {'disable_existing_loggers': True,
               'filters': dict(),
               'formatters': {'verbose': {'datefmt': '%Y-%m-%d %H:%M:%S',
                                          'format': LOGGING_FORMAT}},
               'handlers': {'console': {'class': 'logging.StreamHandler',
                                        'debug_only': True,
                                        'formatter': 'verbose'}},
               'incremental': False,
               'loggers': {'helper': {'handlers': ['console'],
                                         'level': 'INFO',
                                         'propagate': True}},
               'root': {'handlers': [],
                        'level': logging.CRITICAL,
                        'propagate': True},
               'version': 1}

    def __init__(self, file_path=None):
        """Create a new instance of the configuration object, passing in the
        path to the configuration file.

        :param str file_path:

        """
        self.application = Data()
        self.daemon = Data()
        self.logging = Data()
        self._file_path = None
        self._values = Data()
        if file_path:
            self._file_path = self._validate(file_path)
            self._values = Data(self._load_config_file())
        self._assign_defaults()
        LOGGER.debug(self.logging)

    def _assign_defaults(self):
        if 'Application' in self._values:
            self.application = self._values['Application']
        else:
            self.application = self.APPLICATION

        if 'Daemon' in self._values:
            self.daemon = self._values['Daemon']
        else:
            self.daemon = self.DAEMON

        if 'Logging' in self._values:
            self.logging = dict(self._values['Logging'])
        else:
            self.logging = self.LOGGING

    def reload(self):
        """Reload the configuration from disk returning True if the
        configuration has changed from the previous values.

        """
        if self._file_path:

            # Try and reload the configuration file from disk
            try:
                values = Data(self._load_config_file())
            except ValueError as error:
                LOGGER.error('Could not reload configuration: %s', error)
                return False

            # Only update the configuration if the values differ
            if cmp(values, self._values) == 0:
                self._values = values
                self._assign_defaults()
                return True

        return False

    def _load_config_file(self):
        """Load the configuration file into memory, returning the content.

        """
        LOGGER.info('Loading configuration from %s', self._file_path)
        try:
            config = open(self._file_path).read()
        except OSError as error:
            raise ValueError('Could not read configuration file: %s' % error)
        try:
            return yaml.safe_load(config)
        except yaml.YAMLError as error:
            raise ValueError('Error in the configuration file: %s' % error)

    def _validate(self, file_path):
        """Normalize the path provided and ensure the file path, raising a
        ValueError if the file does not exist.

        :param str file_path:
        :return: str
        :raises: ValueError

        """
        file_path = path.abspath(file_path)
        if not path.exists(file_path):
            raise ValueError('Configuration file not found: %s' % file_path)
        return file_path


class LoggingConfig(object):
    """The Logging class is used for abstracting away dictConfig logging
    semantics and can be used by sub-processes to ensure consistent logging
    rule application.

    """
    DEBUG_ONLY = 'debug_only'
    HANDLERS = 'handlers'
    LOGGERS = 'loggers'

    def __init__(self, configuration, debug=None):
        """Create a new instance of the Logging object passing in the
        DictConfig syntax logging configuration and a debug flag.

        :param dict configuration: The logging configuration
        :param bool debug: Toggles use of debug_only loggers

        """
        self.config = configuration
        self.debug = debug
        self._configure()

    def update(self, configuration, debug=None):
        """Update the internal configuration values, removing debug_only
        handlers if debug is False. Returns True if the configuration has
        changed from previous configuration values.

        :param dict configuration: The logging configuration
        :param bool debug: Toggles use of debug_only loggers
        :rtype: bool

        """
        if cmp(self.config, configuration) != 0 and debug != self.debug:
            self.config = configuration
            self.debug = debug
            self._configure()
            return True
        return False

    def _configure(self):
        """Configure the Python stdlib logger"""
        if self.debug is not None and not self.debug:
            self._remove_debug_only_handlers()
        self._remove_debug_only_from_handlers()
        logging_config.dictConfig(self.config)
        logging.captureWarnings(True)

    def _remove_debug_only_from_handlers(self):
        """Iterate through each handler removing the invalid dictConfig key of
        debug_only.

        """
        LOGGER.debug('Removing debug only from handlers')
        for handler in self.config[self.HANDLERS]:
            if self.DEBUG_ONLY in self.config[self.HANDLERS][handler]:
                del self.config[self.HANDLERS][handler][self.DEBUG_ONLY]

    def _remove_debug_only_handlers(self):
        """Remove any handlers with an attribute of debug_only that is True and
        remove the references to said handlers from any loggers that are
        referencing them.

        """
        remove = list()
        for handler in self.config[self.HANDLERS]:
            if self.config[self.HANDLERS][handler].get('debug_only'):
                remove.append(handler)
        for handler in remove:
            del self.config[self.HANDLERS][handler]

            for logger in self.config[self.LOGGERS].keys():
                logger = self.config[self.LOGGERS][logger]
                if handler in logger[self.HANDLERS]:
                    logger[self.HANDLERS].remove(handler)
        self._remove_debug_only_from_handlers()


class Data(object):
    """Data object configuration is wrapped in, can be used as a object with
    attributes or as a dict.

    """
    def __init__(self, value=None):
        super(Data, self).__init__()
        if value:
            for name in value:
                setattr(self, name, value)

    def __contains__(self, name):
        return name in self.__dict__.keys()

    def __delattr__(self, name):
        object.__delattr__(self, name)

    def __delitem__(self, name):
        if not name in self.__dict__:
            raise nameError(name)
        object.__delattr__(self, name)

    def __getattribute__(self, name):
        return object.__getattribute__(self, name)

    def __getitem__(self, name):
        return object.__getattribute__(self, name)

    def __setitem__(self, name, value):
        if isinstance(value, dict) and name != '__dict__':
            value = Data(value)
        object.__setattr__(self, name, value)

    def __setattr__(self, name, value):
        if isinstance(value, dict) and name != '__dict__':
            value = Data(value)
        object.__setattr__(self, name, value)

    def __repr__(self):
        return repr(self.__dict__)

    def __len__(self):
        return len(self.__dict__.keys())

    def __iter__(self):
        for name in self.__dict__.keys():
            yield name

    def str(self):
        return str(self.__dict__)

    def dict(self):
        return dict(self.__dict__)

    def copy(self):
        return copy(self.__dict__)

    def get(self, name):
        return self.__dict__.get(name)

    def has_name(self, name):
        return name in self.__dict__

    def items(self):
        return self.__dict__.items()

    def iteritems(self):
        return self.__dict__.iteritems()

    def itervalues(self):
        return self.__dict__.itervalues()

    def keys(self):
        return self.__dict__.keys()

    def pop(self, name, d=None):
        return self.__dict__.pop(name, d)

    def setdefault(self, name, default):
        self.__dict__.setdefault(name, default)

    def update(self, other=None, **kwargs):
        self.__dict__.update(other, **kwargs)

    def values(self):
        return self.__dict__.values()