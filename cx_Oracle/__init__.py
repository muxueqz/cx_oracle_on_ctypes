from decimal import Decimal

from datetime import datetime, date
from datetime import datetime as Timestamp
from datetime import date as Date
import sys

import ctypes
from ctypes import c_int, byref

from custom_exceptions import Warning, Error, InterfaceError, DatabaseError, DataError, OperationalError, IntegrityError, InternalError, ProgrammingError, NotSupportedError

from connection import Connection
connect = Connection # the name "connect" is required by the DB API
from utils import python3_or_better
from numbervar import NUMBER #, NATIVE_FLOAT
from stringvar import STRING, BINARY, FIXED_CHAR, FIXED_UNICODE, ROWID, UNICODE
from longvar import LONG_BINARY, LONG_STRING
from datetimevar import DATETIME
from lobvar import NCLOB, CLOB, BLOB, BFILE
from externallobvar import LOB
from timestampvar import TIMESTAMP
from intervalvar import INTERVAL
from cursorvar import CURSOR

# compatible with cx_Oracle
from oci import OCI_SYSDBA as SYSDBA
from oci import OCI_SYSOPER as SYSOPER

def symbol_exists(symbol_name):
    pass

def makedsn(*args, **kwargs):
    args = list(args)
    args.append(kwargs['sid'])
    format = "(DESCRIPTION=(ADDRESS_LIST=(ADDRESS=(PROTOCOL=TCP)(HOST=%s)(PORT=%s)))(CONNECT_DATA=(SID=%s)))"
    return format % tuple(args)

ORACLE_VERSION_10G, ORACLE_VERSION_10GR2, ORACLE_VERSION_11G = range(3)

ORACLE_VERSION = ORACLE_VERSION_11G

if symbol_exists('OCI_ATTR_MODULE'):
    ORACLE_VERSION = ORACLE_VERSION_10G
if symbol_exists('OCI_MAJOR_VERSION'):
    ORACLE_VERSION = ORACLE_VERSION_10GR2
if symbol_exists('OCI_ATTR_CONNECTION_CLASS'):
    ORACLE_VERSION = ORACLE_VERSION_11G

# broken end! can we try to run the clientversion method instead? apparently, it does not exist for oracle 10g, but if that is the only case, it is still OK

if ORACLE_VERSION >= ORACLE_VERSION_10GR2:
    def clientversion():
        major_version, minor_version, update_num, patch_num, port_update_num = c_int(), c_int(), c_int(), c_int(), c_int()
        the_so.OCIClientVersion(byref(major_version), byref(minor_version), byref(update_num), byref(patch_num), byref(port_update_num))
        
        return (major_version.value, minor_version.value, update_num.value, patch_num.value, port_update_num.value)

def Time(*args):
    raise NotSupportedError("Oracle does not support time only variables")

TimeFromTicks = Time

def DateFromTicks(args):
    return date.fromtimestamp(args)

def TimestampFromTicks(args):
    return datetime.fromtimestamp(args)

apilevel = '2.0'
threadsafety = 2
paramstyle = 'named'
buildtime = '' # TODO: Find out what cx_oracle puts here

version = '0.1'

# TODO: add all exceptions, imported classes etc
__all__ = ['makedsn', 'Time', 'DateFromTicks', 'TimeFromTicks', 'TimestampFromTicks'] # just to hide ancilliary names like "python3_or_better"
if ORACLE_VERSION >= ORACLE_VERSION_10GR2:
    __all__ += ['clientversion']
