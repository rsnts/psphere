# Copyright 2010 Jonathan Kinred <jonathan.kinred@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# he Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging

from suds import MethodNotFound
from psphere import soap
from psphere.errors import ObjectNotFoundError

logger = logging.getLogger("psphere")

class ReadOnlyCachedAttribute(object):
    """Retrieves attribute value from server and caches it in the instance.
    Source: Python Cookbook
    Author: Denis Otkidach http://stackoverflow.com/users/168352/denis-otkidach
    This decorator allows you to create a property which can be computed once
    and accessed many times.
    """
    def __init__(self, method, name=None):
        print("============== Calling for %s" % method.__name__)
        print("==============%s" % name)
        self.method = method
        self.name = name or method.__name__
        self.__doc__ = method.__doc__

    def __get__(self, inst, cls):
        # If we're being accessed from the class itself, not from an object
        if inst is None:
            print("inst is None")
            return self
        # Else if the attribute already exists, return the existing value
        elif self.name in inst.__dict__:
            print("Using cached value for %s" % self.name)
            return inst.__dict__[self.name]
        # Else, calculate the desired value and set it
        else:
            print("Retrieving and caching value for %s" % self.name)
            # TODO: Check if it's an array or a single value
            #result = self.method(inst)
            if inst.properties[self.name]["MOR"] is True:
                if isinstance(inst.properties[self.name]["value"], list):
                    result = inst.server.get_views(inst.properties[self.name])
                else:
                    result = inst.server.get_view(inst.properties[self.name])
            else:
                # It's just a property, get it
                result = inst.properties[self.name]["value"]
                
            # Set the object value to returned value
            inst.__dict__[self.name] = result
            return result

#    def __set__(self, inst, value):
        #raise AttributeError("%s is read-only" % self.name)

    def __delete__(self, inst):
        del inst.__dict__[self.name]


class ManagedObject(object):
    """The base class which all managed object's derive from.
    
       Create a new instance.
       
       Parameters
       ----------
       mo_ref : ManagedObjectReference
           The managed object reference used to create this instance
       server: server
           A reference back to the server object, which we use to make calls
    """
    attrs = {}
    def __init__(self, mo_ref, server):
        logger.debug("===== Have been passed %s as mo_ref: " % mo_ref)
        self.mo_ref = mo_ref
        self.server = server
        self.properties = {}

    def update_view_data(self, properties=None):
        """Update the local object from the server-side object."""
        property_spec = soap.create(self.server.client, 'PropertySpec')
        logger.debug("3Using: %s" % self.mo_ref._type)
        property_spec.type = str(self.mo_ref._type)
        if not properties and self.server.auto_populate:
            property_spec.all = True
        else:
            property_spec.all = False
            property_spec.pathSet = properties

        object_spec = soap.create(self.server.client, 'ObjectSpec')
        logger.debug("2Using: %s" % self.mo_ref)
        object_spec.obj = self.mo_ref

        pfs = soap.create(self.server.client, 'PropertyFilterSpec')
        pfs.propSet = [property_spec]
        pfs.objectSet = [object_spec]

        object_contents = self.server.sc.propertyCollector.RetrieveProperties(
            specSet=pfs)
        if not object_contents:
            # TODO: Improve error checking and reporting
            print('The view could not be updated.')
        for object_content in object_contents:
            self.set_view_data(object_content)

    def set_view_data(self, object_content):
        """Update the local object from the passed in list."""
        # This is a debugging entry that allows one to view the
        # ObjectContent that this instance was created from
        self._object_content = object_content
        for dynprop in object_content.propSet:
            # If the class hasn't defined the property, don't use it
            if dynprop.name not in self.properties:
                print('WARNING: Skipping undefined property "%s" '
                      'with value "%s"' % (dynprop.name, dynprop.val))
                continue

            try:
                if not len(dynprop.val):
                    logging.debug("DEBUG: Skipping %s with empty value" %
                                  dynprop.name)
                    continue
            except TypeError:
                # This except allows us to pass over:
                # TypeError: object of type 'datetime.datetime' has no len()
                pass

            # Values which contain classes starting with Array need
            # to be converted into a nicer Python list
            if dynprop.val.__class__.__name__.startswith('Array'):
                # suds returns a list containing a single item, which
                # is another list. Use the first item which is the real list
                self.properties[dynprop.name]["value"] = dynprop.val[0]
            else:
                print("-----------------")
                print(dynprop.val.__class__.__name__)
                print("-----------------")
                # At this point we should walk the entire "tree" and set
                # any MOR's to Python classes
                self.properties[dynprop.name]["value"] = dynprop.val

#    def set_view_data(self, object_content):
#        """Update the local object from the passed in list."""
#        # This is a debugging entry that allows one to view the
#        # ObjectContent that this instance was created from
#        self._object_content = object_content
#        for dynprop in object_content.propSet:
#            # If the class hasn't defined the property, don't use it
#            if dynprop.name not in dir(self):
#                print('WARNING: Skipping undefined property "%s" '
#                      'with value "%s"' % (dynprop.name, dynprop.val))
#                continue
#
#            try:
#                if not len(dynprop.val):
#                    logging.debug("DEBUG: Skipping %s with empty value" %
#                                  dynprop.name)
#                    continue
#            except TypeError:
#                # This except allows us to pass over:
#                # TypeError: object of type 'datetime.datetime' has no len()
#                pass
#
#            # Values which contain classes starting with Array need
#            # to be converted into a nicer Python list
#            if dynprop.val.__class__.__name__.startswith('Array'):
#                # suds returns a list containing a single item, which
#                # is another list. Use the first item which is the real list
#                print(dynprop.val.__class__.__name__)
#                if (dynprop.val.__class__.__name__ ==
#                    'ArrayOfManagedObjectReference'):
#                    setattr(self, '_%s' % dynprop.name, dynprop.val[0])
#                else:
#                    setattr(self, dynprop.name, dynprop.val[0])
#            else:
#                print("-----------------")
#                print(dynprop.val.__class__.__name__)
#                print("-----------------")
#                # At this point we should walk the entire "tree" and set
#                # any MOR's to Python classes
#                
#                if (dynprop.val.__class__.__name__ in classmap or
#                    dynprop.val.__class__.__name__ ==
#                    "ManagedObjectReference" or 
#                    dynprop.val.__class__.__name__ == "val"):
#                    setattr(self, '_%s' % dynprop.name, dynprop.val)
#                else:
#                    setattr(self, dynprop.name, dynprop.val)

    def __getattribute__(self, name):
        """Overridden so that SOAP methods can be proxied.
        
        This is achieved by checking if the method exists in the
        SOAP service.
        
        If it doesn't then the exception is caught and the default
        behaviour is executed.
        
        If it does, then a function is returned that will invoke
        the method against the SOAP service with _this set to the
        current objects managed object reference.
        
        """
        # Built-ins always use the default behaviour
        if name.startswith("__"):
            return object.__getattribute__(self, name)

        properties = object.__getattribute__(self, "properties")
        if name in properties.keys():
            # See if the value has already been retrieved an saved
            if name in self.__dict__:
                print("Using cached value for %s" % name)
                return object.__getattribute__(self, name)
            # Else, calculate the desired value and set it
            else:
                print("Retrieving and caching value for %s" % name)
                # TODO: Check if it's an array or a single value
                #result = self.method(inst)
                if self.properties[name]["MOR"] is True:
                    if isinstance(self.properties[name]["value"], list):
                        result = self.server.get_views(self.properties[name]["value"])
                    else:
                        result = self.server.get_view(self.properties[name]["value"])
                else:
                    # It's just a property, get it
                    result = self.properties[name]["value"]
                    
                # Set the object value to returned value
                self.__dict__[name] = result
                return result            
        else:
            try:
                # Here we must manually get the server object so we
                # don't get recursively called when the next method
                # call looks for it
                server = object.__getattribute__(self, "server")
                getattr(server.client.service, name)
                def func(**kwargs):
                    result = self.server.invoke(name, _this=self.mo_ref, **kwargs)
                    return result
        
                return func
            except MethodNotFound:
                return object.__getattribute__(self, name)


# First list the classes which directly inherit from ManagedObject
class AlarmManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(AlarmManager, self).__init__(mo_ref, server)
        self.defaultExpression = []
        self.description = None


class AuthorizationManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(AuthorizationManager, self).__init__(mo_ref, server)
        self.description = None
        self.privilegeList = []
        self.roleList = []


class CustomFieldsManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(CustomFieldsManager, self).__init__(mo_ref, server)
        self.field = []


class CustomizationSpecManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(CustomizationSpecManager, self).__init__(mo_ref, server)
        self.encryptionKey = None
        self.info = []


class DiagnosticManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(DiagnosticManager, self).__init__(mo_ref, server)


class DistributedVirtualSwitchManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(DistributedVirtualSwitchManager, self).__init__(mo_ref, server)


class EnvironmentBrowser(ManagedObject):
    def __init__(self, mo_ref, server):
        super(EnvironmentBrowser, self).__init__(mo_ref, server)
        self._datastoreBrowser = None

    @ReadOnlyCachedAttribute
    def datastoreBrowser(self):
        # TODO: Implement
        pass


class EventManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(EventManager, self).__init__(mo_ref, server)
        self.description = None
        self.latestEvent = None
        self.maxCollector = None


class ExtensibleManagedObject(ManagedObject):
    attrs = {"availableField": {"MOR": False, "value": list()},
             "value": {"MOR": False, "value": list()}}
    def __init__(self, mo_ref, server):
        super(ExtensibleManagedObject, self).__init__(mo_ref, server)
        parent_attrs = super(ExtensibleManagedObject, self).attrs
        self.properties = dict(self.attrs.items() + parent_attrs.items())


class Alarm(ExtensibleManagedObject):
    def __init__(self, mo_ref, server):
        super(Alarm, self).__init__(mo_ref, server)
        self.info = None


class HostCpuSchedulerSystem(ExtensibleManagedObject):
    def __init__(self, mo_ref, server):
        super(HostCpuSchedulerSystem, self).__init__(mo_ref, server)
        self.hyperthreadInfo = None


class HostFirewallSystem(ExtensibleManagedObject):
    def __init__(self, mo_ref, server):
        super(HostFirewallSystem, self).__init__(mo_ref, server)
        self.firewallInfo = None


class HostMemorySystem(ExtensibleManagedObject):
    def __init__(self, mo_ref, server):
        super(HostMemorySystem, self).__init__(mo_ref, server)
        self.consoleReservationInfo = None
        self.virtualMachineReservationInfo = None


class HostNetworkSystem(ExtensibleManagedObject):
    def __init__(self, mo_ref, server):
        super(HostNetworkSystem, self).__init__(mo_ref, server)
        self.capabilites = None
        self.consoleIpRouteConfig = None
        self.dnsConfig = None
        self.ipRouteConfig = None
        self.networkConfig = None
        self.networkInfo = None
        self.offloadCapabilities = None


class HostPciPassthruSystem(ExtensibleManagedObject):
    def __init__(self, mo_ref, server):
        super(HostPciPassthruSystem, self).__init__(mo_ref, server)
        self.pciPassthruInfo = []


class HostServiceSystem(ExtensibleManagedObject):
    def __init__(self, mo_ref, server):
        super(HostServiceSystem, self).__init__(mo_ref, server)
        self.serviceInfo = None


class HostStorageSystem(ExtensibleManagedObject):
    def __init__(self, mo_ref, server):
        super(HostStorageSystem, self).__init__(mo_ref, server)
        self.fileSystemVolumeInfo = None
        self.multipathStateInfo = None
        self.storageDeviceInfo = None
        self.systemFile = None


class HostVirtualNicManager(ExtensibleManagedObject):
    def __init__(self, mo_ref, server):
        super(HostVirtualNicManager, self).__init__(mo_ref, server)
        self.info = None


class HostVMotionSystem(ExtensibleManagedObject):
    def __init__(self, mo_ref, server):
        super(HostVMotionSystem, self).__init__(mo_ref, server)
        self.ipConfig = None
        self.netConfig = None


class ManagedEntity(ExtensibleManagedObject):
    attrs = {"alarmActionsEnabled": {"MOR": False, "value": list()},
             "configIssue": {"MOR": False, "value": list()},
              "configStatus": {"MOR": False, "value": None},
              "customValue": {"MOR": False, "value": list()},
              "declaredAlarmState": {"MOR": False, "value": list()},
              "disabledMethod": {"MOR": False, "value": None},
              "effectiveRole": {"MOR": False, "value": list()},
              "name": {"MOR": False, "value": None},
              "overallStatus": {"MOR": False, "value": None},
              "parent": {"MOR": True, "value": None},
              "permission": {"MOR": False, "value": list()},
              "recentTask": {"MOR": True, "value": list()},
              "tag": {"MOR": False, "value": list()},
              "triggeredAlarmState": {"MOR": False, "value": list()}}
    def __init__(self, mo_ref, server):
        super(ManagedEntity, self).__init__(mo_ref, server)
        parent_attrs = super(ManagedEntity, self).attrs
        self.properties = dict(self.attrs.items() + parent_attrs.items())
        print("New properties: %s" % self.properties.keys())

    def find_datacenter(self, parent=None):
        """Find the datacenter which this ManagedEntity belongs to."""
        # If the parent hasn't been set, use the parent of the
        # calling instance, if it exists
        if not parent:
            if not self.parent:
                raise ObjectNotFoundError('No parent found for this instance')

            # Establish the type of object we need to create
            kls = classmapper(self.parent._type)
            parent = kls(self.parent, self.server)
            parent.update_view_data(properties=['name', 'parent'])

        if not parent.__class__.__name__ == 'Datacenter':
            # Create an instance of the parent class
            kls = classmapper(parent.parent._type)
            next_parent = kls(parent.parent, self.server)
            next_parent.update_view_data(properties=['name', 'parent'])
            # ...and recursively call this method
            parent = self.find_datacenter(parent=next_parent)

        if parent.__class__.__name__ == 'Datacenter':
            return parent
        else:
            raise ObjectNotFoundError('No parent found for this instance')


class ComputeResource(ManagedEntity):
    def __init__(self, mo_ref, server):
        super(ComputeResource, self).__init__(mo_ref, server)
        self.configurationEx = None
        self.datastore = []
        self.environmentBrowser = None
        self.host = []
        self.network = []
        self.resourcePool = None
        self.summary = None

    def find_datastore(self, name):
        if not self.datastore:
            self.update_view_data(self.datastore)

        datastores = self.server.get_views(self.datastore,
                                           properties=['summary'])
        for datastore in datastores:
            if datastore.summary.name == name:
                if self.server.auto_populate:
                    datastore.update_view_data()
                return datastore

        raise ObjectNotFoundError(error='No datastore matching %s' % name)


class ClusterComputeResource(ComputeResource):
    def __init__(self, mo_ref, server):
        super(ClusterComputeResource, self).__init__(mo_ref, server)
        self.actionHistory = []
        self.configuration = None
        self.drsFault = []
        self.drsRecommendation = []
        self.migrationHistory = []
        self.recommendation = []


class Datacenter(ManagedEntity):
    def __init__(self, mo_ref, server):
        super(Datacenter, self).__init__(mo_ref, server)
        self.datastore = []
        self.datastoreFolder = None
        self.hostFolder = None
        self.network = []
        self.networkFolder = None
        self.vmFolder = None


class Datastore(ManagedEntity):
    def __init__(self, mo_ref, server):
        super(Datastore, self).__init__(mo_ref, server)
        self._browser = None
        self.capability = None
        self.host = []
        self.info = None
        self.iormConfiguration = None
        self.summary = None
        self._vm = []

    @ReadOnlyCachedAttribute
    def browser(self):
        result = self.server.get_view(self._browser)
        return result

    @ReadOnlyCachedAttribute
    def vm(self):
        result = self.server.get_views(self._vm)
        return result


class DistributedVirtualSwitch(ManagedEntity):
    def __init__(self, mo_ref, server):
        super(DistributedVirtualSwitch, self).__init__(mo_ref, server)
        self.capability = None
        self.config = None
        self.networkResourcePool = []
        self._portgroup = []
        self.summary = None
        self.uuid = None


    @ReadOnlyCachedAttribute
    def portgroup(self):
        # TODO
        pass


class VmwareDistributedVirtualSwitch(DistributedVirtualSwitch):
    def __init__(self, mo_ref, server):
        super(VmwareDistributedVirtualSwitch, self).__init__(mo_ref, server)


class Folder(ManagedEntity):
    def __init__(self, mo_ref, server):
        super(Folder, self).__init__(mo_ref, server)
        self._childEntity = []
        self.childType = []

    @ReadOnlyCachedAttribute
    def childEntity(self):
        result = self.server.get_views(self._childEntity)
        return result

class HostSystem(ManagedEntity):
    def __init__(self, mo_ref, server):
        super(HostSystem, self).__init__(mo_ref, server)
        self.capability = None
        self.config = None
        self.configManager = None
        self._datastore = []
        self._datastoreBrowser = None
        self.hardware = None
        self._network = []
        self.runtime = None
        self.summary = None
        self.systemResources = None
        self._vm = []

    @ReadOnlyCachedAttribute
    def datastore(self):
        result = self.server.get_views(self._datastore)
        return result

    @ReadOnlyCachedAttribute
    def datastoreBrowser(self):
        result = self.server.get_view(self._datastoreBrowser)
        return result

    @ReadOnlyCachedAttribute
    def network(self):
        result = self.server.get_views(self._network)
        return result

    @ReadOnlyCachedAttribute
    def vm(self):
        result = self.server.get_views(self._vm)
        return result


class Network(ManagedEntity):
    attrs = {"host": {"MOR": True, "value": list()},
             "summary": {"MOR": False, "value": None},
             "vm": {"MOR": True, "value": list()}}
    def __init__(self, mo_ref, server):
        super(Network, self).__init__(mo_ref, server)
        parent_attrs = super(Network, self).attrs
        self.properties = dict(self.attrs.items() + parent_attrs.items())


class DistributedVirtualPortgroup(Network):
    def __init__(self, mo_ref, server):
        super(DistributedVirtualPortgroup, self).__init__(mo_ref, server)
        self.config = None
        self.key = None
        self.portKeys = None


class ResourcePool(ManagedEntity):
    def __init__(self, mo_ref, server):
        super(ResourcePool, self).__init__(mo_ref, server)
        self.config = None
        self.owner = None
        self.resource_pool = []
        self.runtime = None
        self.summary = None
        self.vm = []


class VirtualApp(ResourcePool):
    def __init__(self, mo_ref, server):
        super(VirtualApp, self).__init__(mo_ref, server)
        self.childLink = []
        self._datastore = []
        self._network = []
        self._parentFolder = None
        self._parentVApp = None
        self.vAppConfig = None

    @ReadOnlyCachedAttribute
    def datastore(self):
        result = self.server.get_views(self._datastore)
        return result

    @ReadOnlyCachedAttribute
    def network(self):
        result = self.server.get_views(self._network)
        return result

    @ReadOnlyCachedAttribute
    def parentFolder(self):
        result = self.server.get_view(self._parentFolder)
        return result

    @ReadOnlyCachedAttribute
    def parentVApp(self):
        result = self.server.get_view(self._parentVApp)
        return result


class VirtualMachine(ManagedEntity):
    attrs = {}
    attrs["capability"] = {"MOR": False, "value": None}
    attrs["config"] = {"MOR": False, "value": None}
    attrs["datastore"] = {"MOR": True, "value": list()}
    attrs["environmentBrowser"] = {"MOR": True, "value": None}
    attrs["guest"] = {"MOR": False, "value": None}
    attrs["heartbeatStatus"] = {"MOR": False, "value": None}
    attrs["layout"] = {"MOR": False, "value": None}
    attrs["layoutEx"] = {"MOR": False, "value": None}
    attrs["network"] = {"MOR": True, "value": list()}
    attrs["parentVApp"] = {"MOR": False, "value": None}
    attrs["resourceConfig"] = {"MOR": False, "value": None}
    attrs["resourcePool"] = {"MOR": True, "value": None}
    attrs["rootSnapshot"] = {"MOR": False, "value": list()}
    attrs["runtime"] = {"MOR": False, "value": None}
    attrs["snapshot"] = {"MOR": False, "value": None}
    attrs["storage"] = {"MOR": False, "value": None}
    attrs["summary"] = {"MOR": False, "value": None}
    def __init__(self, mo_ref, server):
        super(VirtualMachine, self).__init__(mo_ref, server)
        parent_attrs = super(VirtualMachine, self).attrs
        self.properties = dict(self.attrs.items() + parent_attrs.items())

    @classmethod
    def from_server(cls, server, name):
        # The caller is expected to catch an ObjectNotFoundError
        obj = server.find_entity_view(cls.__name__, filter={'name': name})
        return obj


class ScheduledTask(ExtensibleManagedObject):
    def __init__(self, mo_ref, server):
        super(ScheduledTask, self).__init__(mo_ref, server)
        self.info = None


class Task(ExtensibleManagedObject):
    def __init__(self, mo_ref, server):
        super(Task, self).__init__(mo_ref, server)
        self.info = None


class VirtualMachineSnapshot(ExtensibleManagedObject):
    def __init__(self, mo_ref, server):
        super(VirtualMachineSnapshot, self).__init__(mo_ref, server)
        self._childSnapshot = []
        self.config = None

    @ReadOnlyCachedAttribute
    def childSnapshot(self):
        result = self.server.get_views(self._childSnapshot)
        return result


class ExtensionManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(ExtensionManager, self).__init__(mo_ref, server)
        self.extensionList = []


class FileManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(FileManager, self).__init__(mo_ref, server)


class HistoryCollector(ManagedObject):
    def __init__(self, mo_ref, server):
        super(HistoryCollector, self).__init__(self, mo_ref, server)
        self.filter = None


class EventHistoryCollector(HistoryCollector):
    def __init__(self, mo_ref, server):
        super(EventHistoryCollector, self).__init__(mo_ref, server)
        self.latestPage = []


class TaskHistoryCollector(HistoryCollector):
    def __init__(self, mo_ref, server):
        super(TaskHistoryCollector, self).__init__(mo_ref, server)
        self.latestPage = []


class HostAutoStartManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(HostAutoStartManager, self).__init__(mo_ref, server)
        self.config = None


class HostBootDeviceSystem(ManagedObject):
    def __init__(self, mo_ref, server):
        super(HostBootDeviceSystem, self).__init__(mo_ref, server)


class HostDatastoreBrowser(ManagedObject):
    def __init__(self, mo_ref, server):
        super(HostDatastoreBrowser, self).__init__(mo_ref, server)
        self._datastore = []
        self.supportedType = []

    @ReadOnlyCachedAttribute
    def datastore(self):
        # TODO
        pass


class HostDatastoreSystem(ManagedObject):
    def __init__(self, mo_ref, server):
        super(HostDatastoreSystem, self).__init__(mo_ref, server)
        self.capabilities = None
        self._datastore = []

    @ReadOnlyCachedAttribute
    def datastore(self):
        # TODO
        pass


class HostDateTimeSystem(ManagedObject):
    def __init__(self, mo_ref, server):
        super(HostDateTimeSystem, self).__init__(mo_ref, server)
        self.dateTimeInfo = None


class HostDiagnosticSystem(ManagedObject):
    def __init__(self, mo_ref, server):
        super(HostDiagnosticSystem, self).__init__(mo_ref, server)
        self.activePartition = None


class HostFirmwareSystem(ManagedObject):
    def __init__(self, mo_ref, server):
        super(HostFirmwareSystem, self).__init__(mo_ref, server)


class HostHealthStatusSystem(ManagedObject):
    def __init__(self, mo_ref, server):
        super(HostHealthStatusSystem, self).__init__(mo_ref, server)
        self.runtime = None


class HostKernelModuleSystem(ManagedObject):
    def __init__(self, mo_ref, server):
        super(HostKernelModuleSystem, self).__init__(mo_ref, server)


class HostLocalAccountManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(HostLocalAccountManager, self).__init__(mo_ref, server)


class HostPatchManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(HostPatchManager, self).__init__(mo_ref, server)


class HostSnmpSystem(ManagedObject):
    def __init__(self, mo_ref, server):
        super(HostSnmpSystem, self).__init__(mo_ref, server)
        self.configuration = None
        self.limits = None


class HttpNfcLease(ManagedObject):
    def __init__(self, mo_ref, server):
        super(HttpNfcLease, self).__init__(mo_ref, server)
        self.error = None
        self.info = None
        self.initializeProgress = None
        self.state = None


class IpPoolManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(IpPoolManager, self).__init__(mo_ref, server)


class LicenseAssignmentManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(LicenseAssignmentManager, self).__init__(mo_ref, server)


class LicenseManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(LicenseManager, self).__init__(mo_ref, server)
        self.diagnostics = None
        self.evaluation = None
        self.featureInfo = []
        self._licenseAssignmentManager = None
        self.licensedEdition = None
        self.licenses = []
        self.source = None
        self.sourceAvailable = None

    @ReadOnlyCachedAttribute
    def licenseAssignmentManager(self):
        # TODO
        pass


class LocalizationManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(LocalizationManager, self).__init__(mo_ref, server)
        self.catalog = []


class OptionManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(OptionManager, self).__init__(mo_ref, server)
        self.setting = []
        self.supportedOptions = []


class OvfManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(OvfManager, self).__init__(mo_ref, server)


class PerformanceManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(PerformanceManager, self).__init__(mo_ref, server)


class Profile(ManagedObject):
    def __init__(self, mo_ref, server):
        super(Profile, self).__init__(mo_ref, server)
        self.complianceStatus = None
        self.config = None
        self.createdTime = None
        self.description = None
        self._entity = []
        self.modifiedTime = None
        self.name = None

    @ReadOnlyCachedAttribute
    def entity(self):
        # TODO
        pass


class ClusterProfile(Profile):
    def __init__(self, mo_ref, server):
        super(ClusterProfile, self).__init__(mo_ref, server)


class HostProfile(Profile):
    def __init__(self, mo_ref, server):
        super(HostProfile, self).__init__(mo_ref, server)
        self._referenceHost = None

    @ReadOnlyCachedAttribute
    def referenceHost(self):
        # TODO
        pass


class ProfileComplianceManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(ProfileComplianceManager, self).__init__(mo_ref, server)


class ProfileManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(ProfileManager, self).__init__(mo_ref, server)
        self._profile = []

    @ReadOnlyCachedAttribute
    def profile(self):
        # TODO
        pass


class ClusterProfileManager(ProfileManager):
    def __init__(self, mo_ref, server):
        super(ClusterProfileManager, self).__init__(mo_ref, server)


class HostProfileManager(ProfileManager):
    def __init__(self, mo_ref, server):
        super(HostProfileManager, self).__init__(mo_ref, server)


class PropertyCollector(ManagedObject):
    def __init__(self, mo_ref, server):
        super(PropertyCollector, self).__init__(mo_ref, server)
        self._filter = []

    @ReadOnlyCachedAttribute
    def filter(self):
        # TODO
        pass


class PropertyFilter(ManagedObject):
    def __init__(self, mo_ref, server):
        super(PropertyFilter, self).__init__(mo_ref, server)
        self.partialUpdates = None
        self.spec = None


class ResourcePlanningManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(ResourcePlanningManager, self).__init__(mo_ref, server)


class ScheduledTaskManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(ScheduledTaskManager, self).__init__(mo_ref, server)
        self.description = None
        self._scheduledTask = []

    @ReadOnlyCachedAttribute
    def scheduledTask(self):
        # TODO
        pass


class SearchIndex(ManagedObject):
    def __init__(self, mo_ref, server):
        super(SearchIndex, self).__init__(mo_ref, server)


class ServiceInstance(ManagedObject):
    attrs = {"capability": {"MOR": True, "value": None},
             "content": {"MOR": True, "value": None},
             "serverClock": {"MOR": True, "value": None}}
    def __init__(self, mo_ref, server):
        super(ServiceInstance, self).__init__(mo_ref, server)
        parent_attrs = super(ServiceInstance, self).attrs
        self.properties = dict(self.attrs.items() + parent_attrs.items())


class SessionManager(ManagedObject):
    attrs = {"currentSession": {"MOR": False, "value": None},
             "defaultLocale": {"MOR": False, "value": None},
             "message": {"MOR": False, "value": None},
             "messageLocaleList": {"MOR": False, "value": None},
             "sessionList": {"MOR": False, "value": None},
             "supportedLocaleList": {"MOR": False, "value": None}}
    def __init__(self, mo_ref, server):
        super(SessionManager, self).__init__(mo_ref, server)
        parent_attrs = super(SessionManager, self).attrs
        self.properties = dict(self.attrs.items() + parent_attrs.items())


class TaskManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(TaskManager, self).__init__(mo_ref, server)
        self.description = None
        self.maxCollector = None
        self._recentTask = []

    @ReadOnlyCachedAttribute
    def recentTask(self):
        # TODO
        pass


class UserDirectory(ManagedObject):
    def __init__(self, mo_ref, server):
        super(UserDirectory, self).__init__(mo_ref, server)
        self.domainList = None


class View(ManagedObject):
    def __init__(self, mo_ref, server):
        super(View, self).__init__(mo_ref, server)


class ManagedObjectView(View):
    def __init__(self, mo_ref, server):
        super(ManagedObjectView, self).__init__(mo_ref, server)
        self.view = []


class ContainerView(ManagedObjectView):
    def __init__(self, mo_ref, server):
        super(ContainerView, self).__init__(mo_ref, server)
        self._container = None
        self.recursive = None
        self.type = None


class InventoryView(ManagedObjectView):
    def __init__(self, mo_ref, server):
        super(InventoryView, self).__init__(mo_ref, server)


class ListView(ManagedObjectView):
    def __init__(self, mo_ref, server):
        super(ListView, self).__init__(mo_ref, server)


class ViewManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(ViewManager, self).__init__(mo_ref, server)
        self._viewList = []

    @ReadOnlyCachedAttribute
    def viewList(self):
        # TODO
        pass


class VirtualDiskManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(VirtualDiskManager, self).__init__(mo_ref, server)


class VirtualizationManager(ManagedObject):
    def __init__(self, mo_ref, server):
        super(VirtualizationManager, self).__init__(mo_ref, server)
        # TODO: raise DeprecatedWarning


class VirtualMachineCompatibilityChecker(ManagedObject):
    def __init__(self, mo_ref, server):
        super(VirtualMachineCompatibilityChecker, self).__init__(mo_ref, server)


class VirtualMachineProvisioningChecker(ManagedObject):
    def __init__(self, mo_ref, server):
        super(VirtualMachineProvisioningChecker, self).__init__(mo_ref, server)


classmap = dict((x.__name__, x) for x in (
    Alarm,
    AlarmManager,
    AuthorizationManager,
    ClusterComputeResource,
    ClusterProfile,
    ClusterProfileManager,
    ComputeResource,
    ContainerView,
    CustomFieldsManager,
    CustomizationSpecManager,
    Datacenter,
    Datastore,
    DiagnosticManager,
    DistributedVirtualPortgroup,
    DistributedVirtualSwitch,
    DistributedVirtualSwitchManager,
    EnvironmentBrowser,
    EventHistoryCollector,
    EventManager,
    ExtensibleManagedObject,
    ExtensionManager,
    FileManager,
    Folder,
    HistoryCollector,
    HostAutoStartManager,
    HostBootDeviceSystem,
    HostCpuSchedulerSystem,
    HostDatastoreBrowser,
    HostDatastoreSystem,
    HostDateTimeSystem,
    HostDiagnosticSystem,
    HostFirewallSystem,
    HostFirmwareSystem,
    HostHealthStatusSystem,
    HostKernelModuleSystem,
    HostLocalAccountManager,
    HostMemorySystem,
    HostNetworkSystem,
    HostPatchManager,
    HostPciPassthruSystem,
    HostProfile,
    HostProfileManager,
    HostServiceSystem,
    HostSnmpSystem,
    HostStorageSystem,
    HostSystem,
    HostVirtualNicManager,
    HostVMotionSystem,
    HttpNfcLease,
    InventoryView,
    IpPoolManager,
    LicenseAssignmentManager,
    LicenseManager,
    ListView,
    LocalizationManager,
    ManagedEntity,
    ManagedObjectView,
    Network,
    OptionManager,
    OvfManager,
    PerformanceManager,
    Profile,
    ProfileComplianceManager,
    ProfileManager,
    PropertyCollector,
    PropertyFilter,
    ResourcePlanningManager,
    ResourcePool,
    ScheduledTask,
    ScheduledTaskManager,
    SearchIndex,
    ServiceInstance,
    SessionManager,
    Task,
    TaskHistoryCollector,
    TaskManager,
    UserDirectory,
    View,
    ViewManager,
    VirtualApp,
    VirtualDiskManager,
    VirtualizationManager,
    VirtualMachine,
    VirtualMachineCompatibilityChecker,
    VirtualMachineProvisioningChecker,
    VirtualMachineSnapshot,
    VmwareDistributedVirtualSwitch,
))


def classmapper(name):
    return classmap[name]
