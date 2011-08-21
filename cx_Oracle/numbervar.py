import ctypes
from ctypes import byref
from decimal import Decimal

from variable_type import VariableType
from utils import python3_or_better, cxString_from_ascii, cxString_from_encoded_string
from buffer import cxBuffer
from transforms import oracle_number_to_python_float
import oci

class NUMBER(object):
    pass

# TODO: #ifdef SQLT_BFLOAT whatever
class NATIVE_FLOAT(object):
    pass

# variable type declarations
class BaseNumberVarType(VariableType):
    def __init__(self):
        VariableType.__init__(self)
        #self.oci_type = None
        self.initialize_proc = None
        self.finalize_proc = None
        #self.pre_define_proc = self.pre_define
        self.post_define_proc = None
        self.pre_fetch_proc = None
        self.is_null_proc = None
        self.set_value_proc =  self.set_value
        self.get_value_proc =  self.get_value
        self.get_buffer_size_proc = None

        self.can_be_copied = True
        self.can_be_in_array = True


    def pre_define(self, var, param):
        """Set the type of value (integer, float or string) that will be returned when values are fetched from this variable."""

        # if the return type has not already been specified, check to see if the
        # number can fit inside an integer by looking at the precision and scale
        if var.type is vt_Float:
            c_scale = oci.sb1()
            c_precision = oci.sb2()

            status = oci.OCIAttrGet(param, oci.OCI_HTYPE_DESCRIBE, byref(c_scale), 0, oci.OCI_ATTR_SCALE, var.environment.error_handle)
            var.environment.check_for_error(status, "NumberVar_PreDefine(): scale")
            scale = c_scale.value

            status = oci.OCIAttrGet(param, oci.OCI_HTYPE_DESCRIBE, byref(c_precision), 0, oci.OCI_ATTR_PRECISION, var.environment.error_handle)
            var.environment.check_for_error(status, "NumberVar_PreDefine(): precision")
            precision = c_precision.value

            if scale == 0 or (scale == -127 and precision == 0):
                var.type = vt_LongInteger
            
                if not python3_or_better():
                    if 0 < precision < 10:
                        var.type = vt_Integer

    def get_value(self, var, pos):
        """Returns the value stored at the given array position."""
        if not python3_or_better():
            types = (vt_Boolean, vt_Integer)
        else:
            types = (vt_Boolean, )

        typed_data = self.get_typed_data(var)
        
        if var.type in types:
            c_integer_value = ctypes.c_long()
            status = oci.OCINumberToInt(var.environment.error_handle, byref(typed_data[pos]), ctypes.sizeof(c_integer_value), oci.OCI_NUMBER_SIGNED, byref(c_integer_value))
            integer_value = c_integer_value.value
            var.environment.check_for_error(status, "NumberVar_GetValue(): as integer")

            if not python3_or_better():
                if var.type is vt_Integer:
                    return integer_value
        
            return bool(integer_value)

        if var.type in (vt_NumberAsString, vt_LongInteger):
            c_string = ctypes.create_string_buffer(200)
            c_string_length = oci.ub4()
            c_string_length.value = ctypes.sizeof(c_string)

            typed_data = ctypes.cast(var.data, oci.POINTER(self.oci_type))
            status = oci.OCINumberToText(var.environment.error_handle, byref(typed_data[pos]), var.environment.numberToStringFormatBuffer.c_struct.ptr,
                                     var.environment.numberToStringFormatBuffer.c_struct.size, None, 0, byref(c_string_length), c_string)
            var.environment.check_for_error(status, "NumberVar_GetValue(): as string")

            python_string = c_string.value

            unicode_str = cxString_from_encoded_string(python_string, var.environment.encoding)

            if var.type is vt_NumberAsString:
                return unicode_str

            try:
                return int(unicode_str)
            except ValueError:
                pass

        return oracle_number_to_python_float(var.environment, byref(typed_data[pos]))

    def set_value(self, var, pos, value):
        """Set the value of the variable."""
        
        mapping = {
                    long: self.set_value_from_long,
                    bool: self.set_value_from_boolean,
                    float: self.set_value_from_float,
                    Decimal: self.set_value_from_decimal,
                   }
        
        if not python3_or_better():
            mapping[int] = self.set_value_from_integer
            
        for type, method in mapping.iteritems():
            if isinstance(value, type):
                break
        else:
            method = None
        
        if method is not None:
            return method(var, pos, value)
        
        raise TypeError("expecting numeric data")
    
    def set_value_from_long(self, var, pos, value):
        text_value = str(value)
        text_buffer = cxBuffer.new_from_object(text_value, var.environment.encoding)
        
        typed_data = self.get_typed_data(var)
        
        status = oci.OCINumberFromText(var.environment.error_handle, text_buffer.c_struct.ptr, 
                    text_buffer.c_struct.size, var.environment.numberFromStringFormatBuffer.c_struct.ptr,
                    var.environment.numberFromStringFormatBuffer.c_struct.size, None, 0, 
                    byref(typed_data[pos]))
        
        return var.environment.check_for_error(status, "NumberVar_SetValueFromLong()")
    
    def set_value_from_boolean(self, var, pos, value):
        raise NotImplementedError()
    
    def set_value_from_float(self, var, pos, value):
        double_value = ctypes.c_double(value)
        typed_data = self.get_typed_data(var)
        
        status = oci.OCINumberFromReal(var.environment.error_handle, byref(double_value),
                ctypes.sizeof(double_value), byref(typed_data[pos]))
        return var.environment.check_for_error(status, "NumberVar_SetValueFromFloat()")
    
    def get_typed_data(self, var):
        return ctypes.cast(var.data, oci.POINTER(self.oci_type))
    
    def get_format_and_text_from_decimal(self, tuple_value):
        """Return the number format and text to use for the Decimal object."""
    
        # acquire basic information from the value tuple
        sign, digits, scale = tuple_value
        num_digits = len(digits)
    
        # allocate memory for the string and format to use in conversion
        length = num_digits + abs(scale) + 3
        text_list = []

        format_list = []

        # populate the string and format
        if sign:
            text_list.append('-')
        for i in xrange(num_digits + scale):
            format_list.append('9')
            if i < num_digits:
                digit = digits[i]
            else:
                digit = 0
            
            text_list.append(str(digit))
        
        if scale < 0:
            format_list.append('D')
            text_list.append('.')
            for i in xrange(scale, 0):
                format_list.append('9')
                if num_digits + i < 0:
                    digit = 0
                else:
                    digit = digits[num_digits + i]
                
                text_list.append(str(digit))
        
        text_obj = cxString_from_ascii(''.join(text_list))
        format_obj = cxString_from_ascii(''.join(format_list))
        
        return text_obj, format_obj
    
    def set_value_from_decimal(self, var, pos, value):
        tuple_value = value.as_tuple()
        text_value, format = self.get_format_and_text_from_decimal(tuple_value)
        text_buffer = cxBuffer.new_from_object(text_value, var.environment.encoding)
        format_buffer = cxBuffer.new_from_object(format, var.environment.encoding)
        
        typed_data = self.get_typed_data(var)
        
        status = oci.OCINumberFromText(var.environment.error_handle,
                text_buffer.c_struct.ptr, text_buffer.c_struct.size, format_buffer.c_struct.ptr,
                format_buffer.c_struct.size, var.environment.nlsNumericCharactersBuffer.c_struct.ptr,
                var.environment.nlsNumericCharactersBuffer.c_struct.size, byref(typed_data[pos]))

        return var.environment.check_for_error(status, "NumberVar_SetValueFromDecimal()")
    
    if not python3_or_better():
        def set_value_from_integer(self, var, pos, value):
            """Set the value of the variable from a Python integer."""
            c_integer_value = ctypes.c_long(value)
            
            typed_data = self.get_typed_data(var)
            
            status = oci.OCINumberFromInt(var.environment.error_handle, byref(c_integer_value),
                    ctypes.sizeof(c_integer_value), oci.OCI_NUMBER_SIGNED, byref(typed_data[pos]))
            
            var.environment.check_for_error(status, "NumberVar_SetValueFromInteger()")

class FloatVarType(BaseNumberVarType):
    def __init__(self):
        BaseNumberVarType.__init__(self)
        self.oci_type = oci.OCINumber
        
        self.pre_define_proc = self.pre_define
        self.python_type = NUMBER
        self.oracle_type = oci.SQLT_VNU
        self.charset_form = oci.SQLCS_IMPLICIT
        self.size = ctypes.sizeof(self.oci_type)
        
        self.is_character_data = False
        self.is_variable_length = False


vt_Float = FloatVarType()
vt_Boolean = FloatVarType()

if not python3_or_better():
    vt_Integer = FloatVarType()

vt_LongInteger = FloatVarType()

vt_NumberAsString = FloatVarType()