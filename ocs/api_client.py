""" A module for implementing specific api client for openshift.

This module has an abstract base class which imposes a contract on
methods to be implementedin derived classes which are specific to api client.

"""


import logging
from abc import ABCMeta, abstractmethod


logger = logging.getLogger(__name__)


def get_api_client(client_name):
    """ Get corresponding client object with given name

    Args:
        client_name (str): name of the api client to be instantiated

    Returns:
        api client object
    """
    res = filter(
        lambda x: x.__name__ == client_name,
        APIClientBase.__subclasses__()
    )

    try:
        cls = next(res)
        return cls()
    except StopIteration:
        logger.error(f'Could not find api-client {client_name}')
        raise


class APIClientBase(metaclass=ABCMeta):
    """ Abstract base class for all api-client classes

    This is an abstract base class and api-client specific classes
    should implement all the methods for interacting with openshift cluster

    """

    @property
    @abstractmethod
    def name(self):
        """Concrete class will have api-client name"""
        pass

    @abstractmethod
    def rook_get(self):
        raise NotImplementedError("rook_get method is not implemented")

    @abstractmethod
    def rook_post(self):
        raise NotImplementedError("rook_post method is not implemented")

    @abstractmethod
    def rook_delete(self):
        raise NotImplementedError("rook_delete method is not implemented")

    @abstractmethod
    def rook_patch(self):
        raise NotImplementedError("rook_patch method is not implemented")

    @abstractmethod
    def rook_create(self):
        raise NotImplementedError("rook_create method is not implemented")

    @abstractmethod
    def get_pods(self, **kwargs):
        """ Because of discrepancies in IO format of each client
        leaving this to be implemented by specific client

        Returns:
            list: of pod names
        """
        raise NotImplementedError("get_pods method is not implemented")

    @abstractmethod
    def get_labels(self, pod_name, pod_namespace):
        """ Get the k8s labels on a given pod
        Args:
            pod_name(str): Name of pod
            pod_namespace(str): namespace of pod

        Returns:
           labels: dict()
            """
        raise NotImplementedError("get_labels method is not implemented")


# All openshift REST client specific imports starts here
from oc import openshift_ops
from openshift.dynamic import DynamicClient, exceptions

class OCRESTClient(APIClientBase):
    """ All activities using openshift REST client"""

    def __init__(self):
        """TODO: get REST client instance from ctx which is shared globally"""
        self.rest_client = openshift_ops.OCP()

    @property
    def name(self):
        return "OCRESTClient"

    def get_pods(self, **kwargs):
        """ get pods in specific namespace or across oc cluster

        Args:
            **kwargs: ex: namespace=rook-ceph, label_selector='x==y'

        Returns:
            list: of pods names

            if no namespace provided then this function returns all pods
            across openshift cluster
            """
        resource = self.rest_client.v1_pods
        try:
            pod_data = self.rook_get(resource, **kwargs)
        except exceptions.NotFoundError:
            logger.error("Failed to get pods: resource not found")
            raise
        except Exception:
            logger.error("Unexpected error")
            raise

        return [item.metadata.name for item in pod_data.items]

    def get_labels(self, pod_name, pod_namespace):
        """

        Args:
            pod_name (str)
            pod_namespace:

        Returns:
            labels (dict)
        """
        resource = self.rest_client.v1_pods.status
        labels = dict()
        try:
            pod_meta = self.rook_get(
                resource,
                name=pod_name,
                namespace=pod_namespace,
            )
        except exceptions.NotFoundError:
            logger.error("Failed to get pods: resource not found")
            raise
        except Exception:
            logger.error("Unexpected error")
            raise

        data = pod_meta['metadata']['labels']
        pod_labels = {k: v for k, v in data.items()}
        return pod_labels

    def rook_get(self, resource, **kw):
        return self.rest_client.get(resource, **kw)

    def rook_post(self, **kw):
        pass

    def rook_delete(self, **kw):
        pass

    def rook_patch(self, **kw):
        pass

    def rook_create(self, **kw):
        pass


class OCCLIClient(APIClientBase):
    """ All activities using oc-cli.

    This implements all functionalities like create, patch, delete using
    oc commands.

    """

    @property
    def name(self):
        return "OCCLIClient"


class KubClient(APIClientBase):
    """ All activities using upstream kubernetes client
    """

    @property
    def name(self):
        return "KubClient"
