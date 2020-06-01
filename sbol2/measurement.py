from .constants import *
from .identified import Identified
from .property import LiteralProperty, URIProperty

from rdflib import URIRef


class Measurement(Identified):
    """The purpose of the Measure class is to link a numerical value
    to a unit of measure."""

    def __init__(self, uri=URIRef('example'), value='0.0',
                 unit='', version=VERSION_STRING):
        super().__init__(SBOL_MEASURE, uri, version)
        self.value = LiteralProperty(self, SBOL_VALUE, '1', '1', [], value)
        self.unit = URIProperty(self, SBOL_UNIT, '1', '1', [], unit)
        self.types = URIProperty(self, SBOL_TYPES, '0', '*', [])

    def addType(self, new_type):
        val = self.types
        val.append(new_type)
        self.types = val

    def removeType(self, index=0):
        val = self.types
        del val[index]
        self.types = val
