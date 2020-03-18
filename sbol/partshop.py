import getpass
import logging
import os

import requests
# For backward compatible HTTPError
import urllib3.exceptions

from .config import Config
from .config import ConfigOptions
from .config import parseURLDomain
from .constants import *
from .sbolerror import SBOLError
from .sbolerror import SBOLErrorCode


class PartShop:
    """A class which provides an API front-end for
    online bioparts repositories"""

    def __init__(self, url, spoofed_url=''):
        """

        :param url: The URL of the online repository (as a str)
        :param spoofed_url:
        """
        # initialize member variables
        self.resource = self._validate_url(url, 'resource')
        self.user = ''
        self.key = ''
        self.spoofed_resource = self._validate_url(spoofed_url, 'spoofed')

    def _validate_url(self, url, url_name):
        # This feels like a weak validation
        # Should we verify that it is a string?
        #   [1, 2, 3] will pass this test, and surely break something else later.
        # Should we use urllib.parse.urlparse?
        #   It doesn't do a whole lot, but catches some things this code doesn't
        if len(url) > 0 and url[-1] == '/':
            msg = ('PartShop initialization failed. The {} URL '
                   + 'should not contain a terminal backlash')
            msg = msg.format(url_name)
            raise SBOLError(msg, SBOLErrorCode.SBOL_ERROR_INVALID_ARGUMENT)
        return url

    @property
    def logger(self):
        logger = logging.getLogger('sbol')
        if not logger.hasHandlers():
            # If there are no handlers, nobody has initialized
            # logging.  Configure logging here so we have a chance of
            # seeing the messages.
            logging.basicConfig()
        return logger

    def count(self):
        """Return the count of objects contained in a PartShop"""
        raise NotImplementedError('Not yet implemented')

    def spoof(self, spoofed_url):
        self.spoofed_resource = self._validate_url(spoofed_url, 'spoofed')

    def sparqlQuery(self, query):
        """
        Issue a SPARQL query
        :param query: the SPARQL query
        :return: the HTTP response object
        """
        endpoint = parseURLDomain(self.resource) + '/sparql'
        if self.spoofed_resource == '':
            resource = self.resource
        else:
            resource = self.spoofed_resource
        p = query.find('WHERE')
        if p != -1:
            from_clause = ' FROM <' + parseURLDomain(resource) + \
                          '/user/' + self.user + '> '
            query = query[:p].rstrip() + from_clause + query[p:].lstrip()
        headers = {'X-authorization': self.key, 'Accept': 'application/json'}
        params = {'query': query}  # should handle encoding the query
        if Config.getOption(ConfigOptions.VERBOSE.value) is True:
            self.logger.debug('Issuing SPARQL: ' + query)
        response = requests.get(endpoint, headers=headers, params=params)
        if not response:
            raise SBOLError(SBOLErrorCode.SBOL_ERROR_BAD_HTTP_REQUEST,
                            response)
        return response

    def pull(self, uris, doc, recursive=True):
        """Retrieve an object from an online resource
        :param uris: A list of SBOL objects you want to retrieve,
        or a single SBOL object URI
        :param doc: A document to add the data to
        :param recursive: Whether the GET request should be recursive
        :return: nothing (doc parameter is updated, or an exception is thrown)
        """
        # IMPLEMENTATION NOTE: rdflib.Graph.parse() actually lets you
        # pass a URL as an argument. I decided to not use this method,
        # because I couldn't find an easy way to get the response
        # code, set HTTP headers, etc. In addition, I would need
        # to use requests for submitting new SBOL data anyway.
        endpoints = []
        if type(uris) is str:
            endpoints.append(uris)
        elif type(uris) is list:
            endpoints = uris
        else:
            raise TypeError('URIs must be str or list. Found: ' + str(type(uris)))
        for uri in endpoints:
            try:
                query = self._uri2url(uri)
            except SBOLError as err:
                if err.error_code() == SBOLErrorCode.SBOL_ERROR_INVALID_ARGUMENT:
                    # Assume user has only specified displayId
                    query = self.resource + '/' + uri
                else:
                    raise
            query += '/sbol'
            if not recursive:
                query += 'nr'
            if Config.getOption(ConfigOptions.VERBOSE.value):
                self.logger.debug('Issuing GET request ' + query)
            # Issue GET request
            response = requests.get(query,
                                    headers={'X-authorization': self.key,
                                             'Accept': 'text/plain'})
            if response.status_code == 404:
                raise SBOLError(SBOLErrorCode.SBOL_ERROR_NOT_FOUND,
                                'Part not found. Unable to pull: ' + query)
            elif response.status_code == 401:
                raise SBOLError(SBOLErrorCode.SBOL_ERROR_HTTP_UNAUTHORIZED,
                                'Please log in with valid credentials')
            elif not response:
                raise SBOLError(SBOLErrorCode.SBOL_ERROR_BAD_HTTP_REQUEST, response)
            # Add content to document
            serialization_format = Config.getOption('serialization_format')
            Config.setOption('serialization_format', serialization_format)
            doc.readString(response.content)
            doc.resource_namespaces.add(self.resource)

    def submit(self, doc, collection='', overwrite=0):
        """Submit a SBOL Document to SynBioHub
        :param doc: The Document to submit
        :param collection: The URI of a SBOL Collection to which the Document
        contents will be uploaded
        :param overwrite: An integer code: 0 (default) - do not overwrite,
        1 - overwrite, 2 - merge
        :return: the HTTP response object
        """
        if collection == '':
            # If a Document is submitted as a new collection,
            # then Document metadata must be specified
            if len(doc.displayId) == 0 or len(doc.name) == 0 \
                    or len(doc.description) == 0:
                raise SBOLError(SBOLErrorCode.SBOL_ERROR_INVALID_ARGUMENT,
                                'Cannot submit Document. The Document must be '
                                'assigned a displayId, name, and ' +
                                'description for upload.')
        else:
            if len(self.spoofed_resource) > 0 and self.resource in collection:
                # Correct collection URI in case a spoofed resource is being used
                collection = collection.replace(self.resource,
                                                self.spoofed_resource)
            if Config.getOption(ConfigOptions.VERBOSE.value) is True:
                self.logger.info('Submitting Document to an existing collection: %s',
                                 collection)
        # if Config.getOption(ConfigOptions.SERIALIZATION_FORMAT.value) == 'rdfxml':
        #     self.addSynBioHubAnnotations(doc)
        files = {}
        if len(doc.displayId) > 0:
            files['id'] = (None, doc.displayId)
        if len(doc.version) > 0:
            files['version'] = (None, doc.version)
        if doc.name and len(doc.name) > 0:
            files['name'] = (None, doc.name)
        if doc.description and len(doc.description) > 0:
            files['description'] = (None, doc.description)
        citations = ''
        for citation in doc.citations:
            citations += citation + ','
        citations = citations[0:-1]  # chop off final comma
        files['citations'] = (None, citations)
        keywords = ''
        for kw in doc.keywords:
            keywords += kw + ','
        keywords = keywords[0:-1]
        files['keywords'] = (None, keywords)
        files['overwrite_merge'] = (None, str(overwrite))
        files['user'] = (None, self.key)
        files['file'] = ('file', doc.writeString(), 'text/xml')
        if collection != '':
            files['rootCollections'] = (None, collection)
        # Send POST request
        # print(files)
        response = requests.post(self.resource + '/submit',
                                 files=files,
                                 headers={'Accept': 'text/plain',
                                          'X-authorization': self.key})
        # print(response.text)
        if response:
            return response
        elif response.status_code == 401:
            # Raise a urllib3 HTTPError exception to be backward compatible with pySBOL
            raise urllib3.exceptions.HTTPError('You must login with valid credentials '
                                               'before submitting')
        else:
            # Raise a urllib3 HTTPError exception to be backward compatible with pySBOL
            raise urllib3.exceptions.HTTPError('HTTP post request failed with: ' +
                                               str(response.status_code) +
                                               ' - ' + str(response.content))

    def _uri2url(self, uri):
        """Converts an SBOL URI to a URL for running queries to a SynBioHub
        endpoint.

        """
        if self.resource in uri:
            return uri
        if parseURLDomain(self.resource) in uri:
            return uri
        if self.spoofed_resource and self.spoofed_resource in uri:
            return uri.replace(self.spoofed_resource, self.resource)
        msg = ('{} does not exist in the resource namespace')
        msg = msg.format(uri)
        raise SBOLError(msg, SBOLErrorCode.SBOL_ERROR_INVALID_ARGUMENT)

    def remove(self, uri):
        query = self._uri2url(uri)
        url = '{}/remove'.format(query)
        headers = {
            'X-authorization': self.key,
            'Accept': 'application/json'
        }
        response = requests.get(url, headers=headers)
        if response.ok:
            return True
        if response.status_code == 401:
            # TODO: Is there a symbol we can use instead of 401?
            msg = 'You must login with valid credentials before removing'
            raise SBOLError(msg, SBOLErrorCode.SBOL_ERROR_HTTP_UNAUTHORIZED)
        # Not sure what went wrong
        raise SBOLError(msg, SBOLErrorCode.SBOL_ERROR_BAD_HTTP_REQUEST)

    def login(self, user_id, password=''):
        """In order to submit to a PartShop, you must login first.
        Register on [SynBioHub](http://synbiohub.org) to
        obtain account credentials.
        :param user_id: User ID
        :param password: User password
        :return: the HTTP response object
        """
        self.user = user_id
        if password is None or password == '':
            password = getpass.getpass()
        response = requests.post(
            parseURLDomain(self.resource) + '/remoteLogin',
            data={'email': user_id, 'password': password},
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        if not response:
            msg = 'Login failed due to an HTTP error: {}'
            msg = msg.format(response)
            raise SBOLError(msg, SBOLErrorCode.SBOL_ERROR_BAD_HTTP_REQUEST)
        self.key = response.content.decode('utf-8')
        return response

    def getKey(self):
        return self.key

    def getURL(self):
        return self.resource

    # For backward compatibility with pySBOL
    def getUser(self):
        return self.user

    # For backward compatibility with pySBOL
    def getSpoofedURL(self):
        return self.spoofed_resource

    # def addSynBioHubAnnotations(self, doc):
    #     doc.addNamespace("http://wiki.synbiohub.org/wiki/Terms/synbiohub#", "sbh")
    #     for id, toplevel_obj in doc.SBOLObjects:
    #         toplevel_obj.apply(None, None)  # TODO
