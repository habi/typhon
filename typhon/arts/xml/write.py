# -*- coding: utf-8 -*-

"""Write ARTS XML types

This package contains the internal implementation for writing ARTS XML files.
"""

from __future__ import absolute_import

import numpy as np

from .names import *

__all__ = ['ARTSXMLWriter']


def get_arts_typename(var):
    """Returns the ARTS type name for this variable.

    Args:
        var: Variable to get the ARTS type name for.

    Returns:
        str: ARTS type name.

    """
    if type(var).__name__ in basic_types:
        ret = basic_types[type(var).__name__]
        if ret == 'Array':
            ret = 'ArrayOf' + get_arts_typename(var[0])
    elif type(var) is np.ndarray:
        ret = tensor_names[var.ndim - 1]
    else:
        ret = type(var).__name__

    return ret


class ARTSXMLWriter:
    """Class to output a variable to an ARTS XML file."""

    def __init__(self, fp, precision='.7e', binaryfp=None):
        self.filepointer = fp
        self.precision = precision
        self.binaryfilepointer = binaryfp
        self._tag_stack = []

    @property
    def filepointer(self):
        """TextIOWrapper: Output file."""
        return self._fp

    @filepointer.setter
    def filepointer(self, fp):
        self._fp = fp

    @property
    def precision(self):
        """str: Floating point output format."""
        return self._precision

    @precision.setter
    def precision(self, fmt):
        self._precision = fmt

    @property
    def binaryfilepointer(self):
        """BufferedWriter: Binary output file."""
        return self._binaryfp

    @binaryfilepointer.setter
    def binaryfilepointer(self, binaryfp):
        self._binaryfp = binaryfp

    def write_header(self, version=1):
        """Write XML file header.

        Writes the XML header and the opening arts tag.

        Args:
            version (int): ARTS XML version.
            filetype (str): ARTS XML file type (e.g. 'ascii', 'binary').

        """
        if self.binaryfilepointer is not None:
            filetype='binary'
        else:
            filetype='ascii'

        self.write('<?xml version="1.0"?>\n')
        self.open_tag('arts', {'version': version, 'format': filetype})

    def open_tag(self, tag, attr=None, newline=True):
        """Write opening tag with attributes.

        Args:
            tag (str): Tag name.
            attr (dict): Optional XML attributes.
            newline (bool): Put newline after tag.
        """
        if attr is None:
            attr = {}
        tagstr = '<{}{}>'.format(tag,
                                 ''.join([' {}="{}"'.format(a, v) for a, v in
                                          attr.items()]))
        if newline:
            tagstr += '\n'

        self._tag_stack.append(tag)
        self.write(tagstr)

    def close_tag(self):
        """Close current XML tag."""
        self.write('</{}>\n'.format(self._tag_stack.pop()))

    def write_footer(self):
        """Write closing tag for ARTS XML file."""
        self.close_tag()

    def write(self, str):
        """Write string to XML file."""
        self.filepointer.write(str)

    def write_xml(self, var, attr=None, arraytype=None):
        """Write a variable as XML.

        Writing basic matpack types is implemented here. Custom types (e.g.
        GriddedFields) must implement a class member function called
        'write_xml'.

        Tuples and list are mapped to ARTS Array types.

        """
        if hasattr(var, 'write_xml'):
            var.write_xml(self, attr)
        elif type(var) is np.ndarray:
            self.write_ndarray(var, attr)
        elif type(var) is int:
            self.write_basic_type('Index', var, attr)
        elif type(var) is float:
            self.write_basic_type('Numeric', var, attr, self.precision)
        elif type(var) is str:
            self.write_basic_type('String', '"' + var + '"', attr)
        elif type(var) in (list, tuple):
            if arraytype is None:
                try:
                    arraytype = get_arts_typename(var[0])
                except IndexError:
                    raise RuntimeError('Array must have at least one element.')

            if attr is None:
                attr = {}
            else:
                attr = attr.copy()
            attr['nelem'] = len(var)
            attr['type'] = arraytype
            self.open_tag('Array', attr)
            for i, v in enumerate(var):
                if get_arts_typename(v) != arraytype:
                    raise RuntimeError(
                        'All array elements must have the same type. '
                        "Array type is '{}', but element {} has type '{}'".format(
                            arraytype, i, get_arts_typename(v)))
                self.write_xml(v)
            self.close_tag()
        else:
            raise TypeError(
                "Can't map '{}' to any ARTS type.".format(type(var).__name__))

    def write_basic_type(self, name, var, attr={}, precision=''):
        """Write a basic ARTS type as XML.

        Args:
            name: Variable type name.
            var: See :meth:`write_xml`.
            attr: See :meth:`write_xml`.
            precision (str): Output format string.

        """
        self.open_tag(name, attr, newline=False)
        if self.binaryfilepointer is not None and name == 'Index':
            np.array(var, dtype='i4').tofile(self.binaryfilepointer)
        elif self.binaryfilepointer is not None and name == 'Numeric':
            np.array(var, dtype='d').tofile(self.binaryfilepointer)
        else:
            self.write(('{:' + precision + '}').format(var))
        self.close_tag()

    def write_ndarray(self, var, attr):
        """Convert ndarray to ARTS XML representation.

        For arguments see :meth:`write_xml`.

        """
        if attr is None:
            attr = {}
        ndim = var.ndim
        tag = get_arts_typename(var)
        # Vector
        if ndim == 1:
            attr['nelem'] = var.shape[0]
            self.open_tag(tag, attr)
            if self.binaryfilepointer is not None:
                np.array(var, dtype='d').tofile(self.binaryfilepointer)
            else:
                fmt = "%" + self.precision
                for i in var:
                    self.write(fmt % i + '\n')
            self.close_tag()
        # Matrix and Tensors
        elif ndim <= len(dimension_names):
            for i in range(0, ndim):
                attr[dimension_names[i]] = var.shape[ndim - 1 - i]

            self.open_tag(tag, attr)

            if self.binaryfilepointer is not None:
                np.array(var, dtype='d').tofile(self.binaryfilepointer)
            else:
                # Reshape for row-based linebreaks in XML file
                if np.prod(var.shape) != 0:
                    if (ndim > 2):
                        var = var.reshape(-1, var.shape[-1])

                    fmt = ' '.join(['%' + self.precision, ] * var.shape[1])

                    for i in var:
                        self.write((fmt % tuple(i) + '\n'))
            self.close_tag()
        else:
            raise RuntimeError(
                'Dimensionality ({}) of ndarray too large for '
                'conversion to ARTS XML'.format(ndim))
