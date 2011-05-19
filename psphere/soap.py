"""
A leaky wrapper for the underlying suds library.
"""

import logging
import sys
import urllib2
import suds

from pprint import pprint

log = logging.getLogger(__name__)

class VimFault(Exception):
    def __init__(self, fault):
        self.fault = fault
        self.fault_type = fault.__class__.__name__
        self._fault_dict = {}
        for attr in fault:
            self._fault_dict[attr[0]] = attr[1]

        Exception.__init__(self, "%s: %s" % (self.fault_type, self._fault_dict))

def _init_logging(level=logging.INFO, handler=logging.StreamHandler):
    """Sets the logging level of underlying suds.client."""
    logger = logging.getLogger("suds.client")
    logger.addHandler(handler)
    logger.setLevel(level)
    #logging.getLogger("suds.wsdl").setLevel(logging.DEBUG)


def get_client(url):
    client = suds.client.Client(url + "/vimService.wsdl")
    client.set_options(location=url)
    return client


def create(client, _type, **kwargs):
    """Create a suds object of the requested _type."""
    obj = client.factory.create("ns0:%s" % _type)
    for key, value in kwargs.items():
        setattr(obj, key, value)
    return obj


def invoke(client, method, **kwargs):
    """Invoke a method on the underlying soap service."""
    try:
        # Proxy the method to the suds service
        result = getattr(client.service, method)(**kwargs)
    except AttributeError, e:
        log.critical("Unknown method: %s" % method)
        sys.exit()
    except urllib2.URLError, e:
        logging.debug(pprint(e))
        logging.debug("A URL related error occurred while invoking the '%s' "
              "method on the VIM server, this can be caused by "
              "name resolution or connection problems." % method)
        logging.debug("The underlying error is: %s" % e.reason[1])
        sys.exit()
    except suds.client.TransportError, e:
        logging.debug(pprint(e))
        logging.debug("TransportError: %s" % e)
    except suds.WebFault, e:
        # Get the type of fault
        print("Fault: %s" % e.fault.faultstring)
        if len(e.fault.faultstring) > 0:
            raise

        detail = e.document.childAtPath("/Envelope/Body/Fault/detail")
        fault_type = detail.getChildren()[0].name
        fault = create(fault_type)
        if isinstance(e.fault.detail[0], list):
            for attr in e.fault.detail[0]:
                setattr(fault, attr[0], attr[1])
        else:
            fault["text"] = e.fault.detail[0]

        raise VimFault(fault)

    return result


class ManagedObjectReference(suds.sudsobject.Property):
    """Custom class to replace the suds generated class, which lacks _type."""
    def __init__(self, _type, value):
        suds.sudsobject.Property.__init__(self, value)
        self._type = _type
