# #!/usr/bin/python
# Copyright 2018 Stavros Sachtouris <saxtouri@grnet.gr>
import re
from kamaki.clients import ClientError
from kamaki.clients.astakos import AstakosClient
from kamaki.clients.cyclades import CycladesClient, CycladesNetworkClient
from kamaki.clients.network import NetworkClient
from kamaki.cli import logging
from kamaki.clients.utils import https
from ansible.module_utils.basic import AnsibleModule


class SNFCloud(AnsibleModule):
    """Clarin-aware Synnefo methods, based on kamaki"""
    _astakos, _cyclades, _network = None, None, None

    def __init__(self, *args, **kw):
        super(SNFCloud, self).__init__(*args, **kw)
        self.token = self.params['cloud_token']
        self.project_id = self.params['project_id']
        self._handle_ssl()
        self._check_project_id()

    # General purpose SNF methods and properties
    def _handle_ssl(self):
        ca_certs = self.params['ca_certs']
        if ca_certs:
            try:
                https.patch_with_certs(ca_certs)
            except Exception as e:
                self.fail_json(
                    msg="Certificates (ca_certs) failed to patch kamaki",
                    msg_details="{}".format(e))
        else:
            https.patch_ignore_ssl()

    def _check_project_id(self):
        """returns: True if project id is there and active, False, otherwise"""
        try:
            project = self.astakos.get_project(self.project_id)
        except ClientError as e:
            msg='Error while checking project id "{}"'.format(self.project_id)
            self.fail_json(msg=msg, msg_details=e.message)
        if project['state'] != 'active':
            msg = 'Project {name} with id {id} is not active (state: {state})'
            self.fail_json(msg=msg.format(
                pname=project['name'], pid=project['id'],
                state=project['state']))
        return True

    @property
    def astakos(self):
        if not self._astakos:
            try:
                self._astakos = AstakosClient(
                    self.params['cloud_url'], self.token)
            except ClientError as e:
                self.fail_json(
                    msg="Astakos Client initialization failed",
                    msg_details=e.message)
        return self._astakos

    @property
    def cyclades(self):
        if not self._cyclades:
            try:
                url = self.astakos.get_endpoint_url('compute')
            except ClientError as e:
                module.fail_json(
                    msg="Cyclades api endpoint retrieval failed",
                    msg_details=e.message)
            try:
                return CycladesClient(url, self.token)
            except ClientError as e:
                module.fail_json(
                    msg="Cyclades Client initialization failed",
                    msg_details=e.message)
        return self._cyclades

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

    def stop_vm(self, vm_id):
        try:
            res = self.cyclades.shutdown_server(vm_id)
        except ClientError as e:
            self.fail_json(msg="Failed to stop VM", msg_details=e.message)
        try:
            new_state = self.cyclades.wait_server_until(vm_id, 'STOPPED')
        except Exception as e:
            new_state = 'UNKNOWN'
        if new_state['status'] == 'STOPPED':
            self.exit_json(
                changed=True, vm_name=self.params['vm_name'], vm_id=vm_id,
                msg="vm is now stopped!")
        self.exit_json(
            changed=True, vm_name=self.params['vm_name'], vm_id=vm_id,
            msg="vm is stopping...")

    def start_vm(self, vm_id):
        try:
            res = self.cyclades.start_server(vm_id)
        except ClientError as e:
            self.fail_json(msg="Failed to start VM", msg_details=e.message)
            return
        if self.params['wait']:
            new_state = self.cyclades.wait_server_until(vm_id, 'ACTIVE')
            if new_state['status'] == 'ACTIVE':
                self.exit_json(
                    changed=True, vm_name=self.params['vm_name'],
                    vm_id=vm_id, msg="vm is now active!")
                return
        self.exit_json(
            changed=True, vm_name=self.params['vm_name'], vm_id=vm_id,
            msg="vm is booting...")

    def discover_vm(self, vm_name):
        try:
            for vm in self.cyclades.list_servers(detail=True):
                if vm_name == vm['name']:
                    return vm
        except ClientError as e:
            self.fail_json(msg="Could not list VMs", msg_details=e.message)
        return None

    def upload_keys_to_keyring(self, keys_path):
        """Check what keys are there, upload what is missing"""
        key_names = None
        if keys_path:
            try:
                existing_keys = map(
                    lambda x: x['keypair'], self.cyclades.list_keypairs())
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
                    new_key = self.cyclades.create_key(
                        key_name=new_key_name, public_key=key)
                except ClientError as e:
                    self.fail_json(
                        msg="Pub key did not upload {} to keyring".format(key),
                        msg_details=e.message)
                key_names.append(new_key_name)
        return key_names

    def create_vm(self, vm_name):
        self.fail_json(changed=False, msg="Not implemented yet")

    def snf_delete_vm(self, vm_id):
        try:
            self.cyclades.delete_server(vm_id)
        except ClientError as e:
            self.fail_json(msg="Error deleting VM", msg_details=e.message)
        try:
            self.cyclades.wait_server_while(vm_id, 'ACTIVE')
            self.exit_json(
                changed=True, msg="VM {} is now deleted!".format(vm_id))
        except ClientError as e:
            self.exit_json(
                changed=True, msg="deleting vm with id {} ...".format(vm_id))


if __name__ == '__main__':
    self.fail_json(changed=False, msg="Not implemented yet")