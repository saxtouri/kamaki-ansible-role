#!/usr/bin/python
# Copyright 2018 Stavros Sachtouris <saxtouri@grnet.gr>
from ansible.module_utils.synnefo import SNFCloud
from kamaki.clients import ClientError
from kamaki.clients.cyclades import CycladesClient, CycladesNetworkClient
from kamaki.clients.network import NetworkClient
from kamaki.cli import logging
from kamaki.clients.utils import https
from ansible.module_utils.basic import AnsibleModule


class SNFPublicIP(SNFCloud):
    """Synnefo network class, based on kamaki
       Create, delete, start, stop, reboot, etc. a private network
    """
    _cyclades, _network = None, None

    def __init__(self, *args, **kw):
        super(SNFPublicIP, self).__init__(*args, **kw)

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
        """Discover the IP with given IP or address"""
        id_, address = self.params.get('id'), self.params.get('address')
        if id_:
            try:
                return self.network.get_floatingip_details(id_)
            except ClientError as e:
                if e.status in (404, ):
                    return None
                self.fail_json(
                    msg='Error while looking for ip', msg_details=e.message)
        elif address:
            for ip in self.network.list_floatingips():
                if address == ip['floating_ip_address']:
                    return ip
        return None

    def reserve(self):
        """Reserve a new floating IP from the pool"""
        try:
            return self.network.create_floatingip(
                floating_ip_address=self.params.get('address'),
                project_id=self.project_id)
        except ClientError as e:
            self.fail_json(
                msg="Failed to create floating IP", msg_details=e.message)

    def next_available(self):
        """Get the next available IP, or reserve a new one"""
        try:
            ips = filter(
                lambda ip: not ip['port_id'], self.network.list_floatingips())
        except ClientError as e:
            self.fail_json('Error while looking for free ips')
        if ips:
            return ips[0]
        return self.reserve()

    def discover_port(self, port_id):
        try:
            return self.network.get_port_details(port_id)
        except ClientError as e:
            self.fail_json(
                msg='Error while checking for port', msg_details=e.message)

    # state functions
    def absent(self):
        """Make sure a given IP is not used
           We do not return IPs back to pool for now
        """
        ip = self.discover()
        if ip:
            port_id = ip['port_id']
            if port_id:
                try:
                    self.network.delete_port(port_id)
                except ClientError as e:
                    self.fail_json(
                        msg='Failed to disconnect IP', msg_details=e.message)
            if self.params.get('wait'):
                try:
                    self.network.wait_port_while(port_id, 'ACTIVE')
                except ClientError:
                    pass
                return dict(changed=True, msg='IP disconnected')
            return dict(changed=False, msg="IP not used")
        return dict(changed=False, msg="No such IP")

    def present(self):
        """Make sure an IP is present if id or address is given
           If no id or address is given, find an unused or fresh IP
        """
        ip = self.discover()
        if ip:
            return dict(changed=False, msg=ip)
        if self.params.get('address'):
            return dict(changed=True, msg=self.reserve())
        return dict(changed=True, msg=self.next_available())

    def connected(self):
        """Make sure this IP is connected to this vm.
           Raise an error if it is already use by some other VM
        """
        ip = self.discover()
        if not ip:
            self.fail_json(msg='No IP found')
        port_id, vm_id = ip['port_id'], self.params.get('vm_id')
        if port_id:
            port = self.discover_port(port_id)
            if port['device_id'] == vm_id:
                return dict(changed=False, msg=port)
            return self.fail_json(msg='IP used by another VM')
        try:
            port = self.network.create_port(
                ip['floating_network_id'], vm_id,
                fixed_ips=[{'ip_address': ip['floating_ip_address']}])
        except ClientError as e:
            self.fail_json(
                msg='Failed to connect IP to VM', msg_details=e.message)
        if self.params.get('wait'):
            try:
                port = self.network.wait_port_until(port['id'], 'ACTIVE')
            except ClientError:
                pass
        return dict(changed=True, msg=port)

    def disconnected(self):
        ip = self.discover()
        if not ip:
            return dict(changed=False, msg='IP not reserved')
        port_id, vm_id = ip['port_id'], self.params.get('vm_id')
        if port_id:
            if vm_id:
                port = self.discover_port(port_id)
                if port['device_id'] != vm_id:
                    return dict(
                        changed=False, msg='IP not connected to this VM')
            try:
                self.network.delete_port(port_id)
            except ClientError as e:
                self.fail_json(
                    msg='Failed to disconnect IP', msg_details=e.message)
            if self.params.get('wait'):
                try:
                    self.network.wait_port_while(port_id, 'ACTIVE')
                except ClientError:
                    pass
            return dict(changed=True, msg='IP disconnected succesfuly')
        return dict(changed=False, msg='IP not connected')


if __name__ == '__main__':
    module = SNFPublicIP(
        argument_spec={
            'state': {
                'default': 'present',
                'choices': ['absent', 'present', 'connected', 'disconnected']},
            'ca_certs': {'required': False, 'type': 'str'},
            'cloud_url': {'required': True, 'type': 'str'},
            'cloud_token': {'required': True, 'type': 'str'},
            'project_id': {'required': True, 'type': 'str'},
            'id': {'required': False, 'type': 'str'},
            'address': {'required': False, 'type': 'str'},
            'vm_id': {'required': False, 'type': 'str'},
            'wait': {'default': True, 'type': 'bool'},
        },
        required_if=(('state', 'connected', ('vm_id', )), )
    )
    result = {
        'absent': module.absent,
        'present': module.present,
        'connected': module.connected,
        'disconnected': module.disconnected,
    }[module.params['state']]()
    module.exit_json(**result)
