#!/usr/bin/python
# Copyright 2018 Stavros Sachtouris <saxtouri@grnet.gr>
from ansible.module_utils.synnefo import SNFCloud
from kamaki.clients import ClientError
from kamaki.clients.cyclades import CycladesClient, CycladesNetworkClient
from kamaki.clients.network import NetworkClient
from kamaki.cli import logging
from kamaki.clients.utils import https
from ansible.module_utils.basic import AnsibleModule


class SNFPrivateNetwork(SNFCloud):
    """Synnefo network class, based on kamaki
       Create, delete, start, stop, reboot, etc. a private network
    """
    _cyclades, _network = None, None

    def __init__(self, *args, **kw):
        super(SNFCloud, self).__init__(*args, **kw)

    @property
    def network(self):
        if not self._network:
            try:
                url = self.astakos.get_endpoint_url('network')
            except ClientError as e:
                self.fail_json(
                    msg="Network api endpoint retrieval failed",
                    msg_details=e.message)
            try:
                self._network = CycladesNetworkClient(url, self.token)
            except ClientError as e:
                self.fail_json(
                    msg="Network Client initialization failed",
                    msg_details=e.message)
        return self._network

    def discover_network(self):
        try:
            for net in self.network.list_networks(detail=True):
                if self.params['name'] == net['name']:
                    return net
        except ClientError as e:
            self.fail_json(
                msg="Could not list networks", msg_details=e.message)
        return None

    def create(self):
        self.fail_json(changed=False, msg="Not implemented yet")

    def delete(self, id):
        try:
            self.cyclades.delete_network(id)
        except ClientError as e:
            self.fail_json(
                msg="Error deleting network", msg_details=e.message)
        self.exit_json(
                changed=True, msg="Network {} is now deleted!".format(id))


if __name__ == '__main__':
    module = SNFPrivateNetwork(
        argument_spec={
            'state': {
                'default': 'present',
                'choices': ['absent', 'present', 'stopped', 'active']},
            'ca_certs': {'required': False, 'type': 'str'},
            'cloud_url': {'required': True, 'type': 'str'},
            'cloud_token': {'required': True, 'type': 'str'},
            'project_id': {'required': False, 'type': 'str'},
            'name': {'required': True, 'type': 'str'},
        }
    )
    module.exit_json(changed=False, msg="Cyclades operation failed".format())
