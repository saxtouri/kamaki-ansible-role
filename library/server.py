#!/usr/bin/python
# Copyright 2018 Stavros Sachtouris <saxtouri@grnet.gr>
from ansible.module_utils.synnefo import SNFCloud
from kamaki.clients import ClientError
from kamaki.clients.cyclades import CycladesClient, CycladesNetworkClient
from kamaki.clients.network import NetworkClient
from kamaki.cli import logging
from kamaki.clients.utils import https
from ansible.module_utils.basic import AnsibleModule


class SNFServer(AnsibleModule):
    """Synnefo server class, based on kamaki
       Create, delete, start, stop, reboot, etc.
    """
    _compute, _network = None, None

    def __init__(self, *args, **kw):
        super(SNFServer, self).__init__(*args, **kw)
        self.cloud = self.params.get('cloud')
        ca_certs = self.cloud.get('ca_certs')
        if ca_certs:
            try:
                https.patch_with_certs(ca_certs)
            except Exception as e:
                self.fail_json(
                    msg="Certificates (ca_certs) failed to patch kamaki",
                    msg_details=e.message)
        else:
            https.patch_ignore_ssl()

    # General purpose SNF methods and properties
    @property
    def compute(self):
        if not self._compute:
            url, token = self.cloud['compute_url'], self.cloud['cloud_token']
            try:
                self._compute = CycladesClient(url, token)
            except ClientError as e:
                module.fail_json(
                    msg="Compute Client initialization failed",
                    msg_details=e.message)
        return self._compute

    @property
    def network(self):
        if not self._network:
            url, token = self.cloud['network_url'], self.cloud['cloud_token']
            try:
                self._network = CycladesNetworkClient(url, token)
            except ClientError as e:
                self.fail_json(
                    msg="Network Client initialization failed",
                    msg_details=e.message)
        return self._network

    # auxiliary methods
    def discover(self):
        id_, name = self.params.get('id'), self.params.get('name')
        if id_:
            try:
                return self.compute.get_server_details(id_)
            except ClientError as e:
                if e.status in (404, ):
                    return None
                self.fail_json(
                    msg='Error while looking up VM', msg_details=e.message)
        try:
            for vm in self.compute.list_servers(detail=True):
                if name == vm['name']:
                    return vm
        except ClientError as e:
            self.fail_json(msg="Could not list VMs", msg_details=e.message)
        return None

    def discover_ip(self):
        """Discover the IP with given IP or address"""
        id_ = self.params.get('public_ip_id')
        if id_:
            try:
                return self.network.get_floatingip_details(id_)
            except ClientError as e:
                if e.status in (404, ):
                    return None
                self.fail_json(
                    msg='Error while looking for ip', msg_details=e.message)
        return None

    def upload_keys_to_keyring(self, keys_path):
        """Check what keys are there, upload what is missing"""
        key_names = None
        if keys_path:
            try:
                existing_keys = map(
                    lambda x: x['keypair'], self.compute.list_keypairs())
            except ClientError as e:
                self.fail_json(
                    msg="Failed to get keypairs", msg_details=e.message)
            with open(keys_path) as f:
                keys = [line.strip() for line in f.readlines() if line.strip()]
            key_names = [key['name'] for key in existing_keys if (
                key['public_key'] in keys)]
            new_keys = set(keys).difference(
                map(lambda x: x['public_key'], existing_keys))
            offset, new_key_name = 1, '{}1'.format(self.KEY_PREFIX)
            for key in new_keys:
                while new_key_name in key_names:
                    offset += 1
                    new_key_name = '{}{}'.format(self.KEY_PREFIX, offset)
                try:
                    new_key = self.compute.create_key(
                        key_name=new_key_name, public_key=key)
                except ClientError as e:
                    self.fail_json(
                        msg="Pub key did not upload {} to keyring".format(key),
                        msg_details=e.message)
                key_names.append(new_key_name)
        return key_names

    def create(self):
        name = self.params.get('name')
        image_id = self.params.get('image_id')
        flavor_id = self.params.get('flavor_id')
        ssh_key = self.params.get('ssh_key')

        net_id = self.params.get('priv_net_id')
        networks = [{'uuid': net_id}] if net_id else []
        ip = self.discover_ip()
        if ip:
            networks.append({
                'uuid': ip['floating_network_id'],
                'floating_ip_address': ip['floating_ip_address']})
        try:
            vm = self.compute.create_server(
                name=name, image_id=image_id, flavor_id=flavor_id,
                project_id=self.cloud.get('project_id'), key_name=ssh_key,
                networks=networks)
        except ClientError as e:
            self.fail_json(
                msg='Failed to create server', msg_details=e.message)
        if self.params.get('wait'):
            try:
                vm = self.compute.wait_server_while(vm['id'], 'BUILD')
            except ClientError as e:
                pass
        return vm

    def delete(self, vm_id):
        try:
            self.compute.delete_server(vm_id)
        except ClientError as e:
            if 'Server has been deleted' not in e.message:
                self.fail_json(
                    msg="Error deleting VM", msg_details=e.message)
        if self.params.get('wait'):
            try:
                self.compute.wait_server_until(vm_id, 'DELETED')
            except ClientError as e:
                pass

    # Functions
    def present(self):
        """Make sure a VM with given features exist
           Create it, if not exist, modify what is modifiable otherwise
        """
        vm, changed = self.discover(), False
        if not vm:
            vm = self.create()
            changed = True
        else:
            name = self.params['name']
            if name and name != vm['name']:
                try:
                    self.compute.update_server_name(vm['id'], name)
                    changed = True
                except ClientError as e:
                    self.fail_json(
                        msg='Failed to changed server name',
                        msg_details=e.message)

            priv_net_id = self.params.get('priv_net_id')
            if priv_net_id and priv_net_id not in vm['addresses']:
                try:
                    port = self.network.create_port(priv_net_id, vm['id'])
                except ClientError as e:
                    self.fail_json(
                        msg='Failed to connect server to network',
                        msg_details=e.message)
                changed = True
                if self.params.get('wait'):
                    try:
                        self.network.wait_port_until(port['id'], 'ACTIVE')
                    except ClientError:
                        pass

            ip = self.discover_ip()
            ip4s = [att['ipv4'] for att in vm['attachments'] if att['ipv4']]
            if ip and ip['floating_ip_address'] not in ip4s:
                try:
                    port = self.network.create_port(
                        ip['floating_network_id'], vm['id'],
                        fixed_ips=[{'ip_address': ip['floating_ip_address']}])
                except ClientError as e:
                    self.fail_json(
                        msg='Failed to attach IP to server',
                        msg_details=e.message)
                if self.params.get('wait'):
                    try:
                        self.network.wait_port_until(port['id'], 'ACTIVE')
                    except ClientError:
                        pass
        return dict(changed=changed, msg=vm)

    def absent(self):
        """Make sure VM is not there (e.g., delete it)"""
        vm = self.discover()
        if not vm:
            return dict(changed=False, msg='VM not found')
        self.delete(vm['id'])
        return dict(changed=True, msg='VM is now deleted')

    def active(self):
        vm = self.discover()
        if not vm:
            self.fail_json(msg='Cannot find VM to start')
        if vm['status'] == 'ACTIVE':
            return dict(changed=False, msg=vm)
        try:
            self.compute.start_server(vm['id'])
        except ClientError as e:
            self.fail_json(msg="Failed to start VM", msg_details=e.message)
            return
        if self.params['wait']:
            try:
                vm = self.compute.wait_server_until(vm['id'], 'ACTIVE')
            except ClientError:
                pass
        return dict(changed=True, msg=vm)

    def stopped(self):
        vm = self.discover()
        if not vm:
            self.fail_json(msg='Cannot find VM to stop')
        if vm['status'] == 'STOPPED':
            return dict(changed=False, msg=vm)
        try:
            self.compute.shutdown_server(vm['id'])
        except ClientError as e:
            self.fail_json(msg="Failed to stop VM", msg_details=e.message)
            return
        if self.params['wait']:
            try:
                vm = self.compute.wait_server_until(vm['id'], 'STOPPED')
            except ClientError:
                pass
        return dict(changed=True, msg=vm)


if __name__ == '__main__':
    module = SNFServer(
        argument_spec={
            'state': {
                'default': 'present',
                'choices': ['present', 'absent', 'stopped', 'active']},
            'cloud': {'required': True, 'type': 'dict'},
            'id': {'required': False, 'type': 'str'},
            'name': {'required': False, 'type': 'str'},
            'image_id': {'required': False, 'type': 'str'},
            'flavor_id': {'required': False, 'type': 'str'},
            'ssh_key': {'required': False, 'type': 'str'},
            'priv_net_id': {'required': False, 'type': 'str'},
            'public_ip_id': {'required': False, 'type': 'str'},
            'wait': {'default': True, 'type': 'bool'},
        },
        required_if=(
            ('state', 'present', ['name', 'image_id', 'flavor_id', ]),
        ),
    )
    result = {
        'absent': module.absent,
        'present': module.present,
        'stopped': module.stopped,
        'active': module.active,
    }[module.params['state']]()
    module.exit_json(**result)
