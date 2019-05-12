from constants import *
from identified import *
import os


class TopLevel(Identified):
    """All SBOL classes derived from TopLevel appear as top level nodes in the RDF/XML document tree and SBOL files."""

    attachments = None

    def __init__(self, type_uri=SBOL_TOP_LEVEL, uri="example", version=VERSION_STRING):
        super().__init__(type_uri, uri, version)
        if Config.getOption(ConfigOptions.SBOL_COMPLIANT_URIS.value) is True:
            self._displayId.set(uri)
            if Config.getOption(ConfigOptions.SBOL_TYPED_URIS.value) is True:
                self._identity.set(os.path.join(getHomespace(), self.getClassName(type_uri), self.displayId, self.version))
                self._persistentIdentity.set(os.path.join(getHomespace(), self.getClassName(type_uri), self.displayId))
            else:
                self._identity.set(os.path.join(getHomespace(), self.displayId, self.version))
                self._persistentIdentity.set(os.path.join(getHomespace(), self.displayId))

    def addToDocument(self, document):
        raise NotImplementedError("Not yet implemented")

    def generateTopLevel(self, uri, agent=None, plan=None, usages=None):
        """ # TODO this originally was called 'generate' but it didn't override parent function of same name.

        :param uri: A URI for the new object, or a displayId if operating in SBOLCompliant mode
        :return:
        """
        raise NotImplementedError("Not yet implemented")

    def initialize(self, uri):
        raise NotImplementedError("Not yet implemented")