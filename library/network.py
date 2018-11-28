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
        super(SNFPrivateNetwork, self).__init__(*args, **kw)

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

    def discover(self):
        id_, name = self.params.get('id'), self.params.get('name')
        if id_:
            try:
                return self.network.get_network_details(id_)
            except ClientError as e:
                if e.status in (404, ):
                    return None
                self.fail_json(
                    msg='Error while looking for network',
                    msg_details=e.message)
        elif name:
            for net in self.network.list_networks(detail=True):
                if name == net['name']:
                    return net
        return None

    def create_subnet(self, id_):
        cidr, dhcp = self.params.get('cidr'), self.params.get('hdcp')
        try:
            return self.network.create_subnet(id_, cidr, enable_dhcp=dhcp)
        except ClientError as e:
            self.fail_json(
                msg="Failed to create subnet=", msg_details=e.message)

    def create(self):
        name = self.params.get('name')
        try:
            return self.network.create_network(
                type='MAC_FILTERED', name=name, project_id=self.project_id)
        except ClientError as e:
            self.fail_json(
                msg="Failed to create network with name {}".format(name),
                msg_details=e.message)

    def discover_port(self, net_id):
        try:
            ports = self.network.list_ports()
        except ClientError as e:
            self.fail_json(msg='Failed to list ports', msg_details=e.message)
        vm_id = self.params.get('vm_id')
        for port in ports:
            if all((
                    port['device_id'] == vm_id,
                    port['network_id'] == net_id)):
                return port

    # state functions
    def absent(self):
        """Make sure a given network does not exist
           Networks are identified by id or name, in that order
        """
        net = self.discover()
        if net:
            try:
                self.network.delete_network(net['id'])
                return dict(changed=True, msg='Network deleted')
            except ClientError as e:
                if e.status not in (404, ):
                    self.fail_json(
                        msg="Error deleting network", msg_details=e.message)
        return dict(changed=False, msg="No such network")

    def present(self):
        """Make sure a network exists (create it, if not)
           If an id and a name are given, the network is identified by the id
           and then its name changes to match the new name.
           If no id is provided, we make sure there exists a network with this
           name
        """
        changed = False
        name = self.params.get('name')
        net = self.discover()
        if not net:
            net = self. create()
            changed = True
        if net['name'] != name:
            try:
                net = self.network.update_network(net['id'], name=name)
            except ClientError:
                self.fail_json(
                    msg="Failed to update network", msg_details=e.message)
            changed = True
        if self.params.get('cidr') and not net['subnets']:
            subnet = self.create_subnet(net['id'])
            net['subnets'].append(subnet['id'])
            changed = True
        return dict(changed=changed, msg=net)

    def connected(self):
        net, vm_id = self.discover(), self.params.get('vm_id')
        if not net:
            self.fail_json(msg='Network does not exist')
        port = self.discover_port(net['id'])
        if port:
            return dict(changed=False, msg=port)
        try:
            port = self.network.create_port(net['id'], vm_id)
        except ClientError as e:
            self.fail_json(
                msg='Failed to connect network', msg_details=e.message)
        if self.params.get('wait'):
            try:
                port = self.network.wait_port_until(port['id'], 'ACTIVE')
            except ClientError as e:
                pass
        return dict(changed=True, msg=port)

    def disconnected(self):
        net = self.discover()
        if not net:
            self.fail_json(msg='Network does not exist')
        port = self.discover_port(net['id'])
        if not port:
            return dict(changed=False, msg='No connection')
        try:
            self.network.delete_port(port['id'])
        except ClientError as e:
            self.fail_json(msg='Failed to delete port', msg_details=e.message)
        if self.params.get('wait'):
            try:
                self.network.wait_port_while(port['id'], 'ACTIVE')
            except ClientError:
                pass
        return dict(changed=True, msg='Disconnected succesfully')


if __name__ == '__main__':
    module = SNFPrivateNetwork(
        argument_spec={
            'state': {
                'default': 'present',
                'choices': ['absent', 'present', 'connected', 'disconnected']},
            'ca_certs': {'required': False, 'type': 'str'},
            'cloud_url': {'required': True, 'type': 'str'},
            'cloud_token': {'required': True, 'type': 'str'},
            'project_id': {'required': True, 'type': 'str'},
            'id': {'required': False, 'type': 'str'},
            'name': {'required': False, 'type': 'str'},
            'cidr': {'required': False, 'type': 'str'},
            'dhcp': {'required': False, 'type': 'bool'},
            'vm_id': {'required': False, 'type': 'str'},
            'wait': {'default': True, 'type': 'bool'},
        },
        required_if=(
            ('dhcp', True, ('cidr', )),
            ('state', 'connected', ('vm_id', )),
            ('state', 'disconnected', ('vm_id', )),
        ),
    )
    result = {
        'absent': module.absent,
        'present': module.present,
        'connected': module.connected,
        'disconnected': module.disconnected,
    }[module.params['state']]()
    module.exit_json(**result)
