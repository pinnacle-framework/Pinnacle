from pinnacledb import logging


class ComponentInUseError(Exception):
    pass


class ComponentInUseWarning(Warning):
    pass


class BaseException(Exception):
    '''
    BaseException which logs a message after
    exception
    '''

    def __init__(self, msg):
        self.msg = msg
        logging.exception(self.msg, e=self)

    def __str__(self):
        return self.msg


class RequiredPackageNotFound(ImportError):

    '''
    Exception raised when one or more required packages are not found.
    '''


class ServiceRequestException(BaseException):
    '''
    ServiceRequestException
    '''


class QueryException(BaseException):
    '''
    QueryException
    '''


class DatabackendException(BaseException):
    '''
    DatabackendException
    '''


class MetadataException(BaseException):
    '''
    MetadataException
    '''


class ComponentException(BaseException):
    '''
    ComponentException
    '''
