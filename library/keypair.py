#!/usr/bin/python
# Copyright 2018 Stavros Sachtouris <saxtouri@grnet.gr>
from kamaki.clients import ClientError
from kamaki.clients.cyclades import CycladesClient, CycladesNetworkClient
from kamaki.cli import logging
from kamaki.clients.utils import https
from datetime import datetime
import uuid
from ansible.module_utils.basic import AnsibleModule


class SNFKeypair(AnsibleModule):
    """Synnefo keypair class, based on kamaki handles PPK pairs"""
    _compute = None

    def __init__(self, *args, **kw):
        super(SNFKeypair, self).__init__(*args, **kw)
        self.cloud = self.params.get('cloud').get('cloud')
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

    def discover(self):
        name = self.params.get('name')
        if name:
            try:
                return self.compute.get_keypair_details(name)
            except ClientError as e:
                if e.status not in (404, ):
                    self.fail_json(
                        msg='Error searching key', msg_details=e.message)
        public_key = self.params.get('public_key')
        if public_key:
            try:
                keypairs = self.compute.list_keypairs()
            except ClientError as e:
                self.fail_json(msg='Error listing keys', msg_details=e.message)
            matching = [k for k in keypairs if k['public_key'] == public_key]
            return matching[0] if matching else None
        return None

    def create(self):
        name = self.params.get('name')
        name = name or 'ansible-autogen_{:%m_%d_%H_%M_%S_%f}_{uniq}'.format(
            datetime.now(), uniq=str(uuid.uuid4())[:8])
        try:
            return self.compute.create_key(
                key_name=name, public_key=self.params.get('public_key'))
        except ClientError as e:
            self.fail_json(
                msg='Failed to upload public key', msg_details=e.message)

    # State functions
    def present(self):
        pair = self.discover()
        return dict(changed=not pair, keypair=pair or self.create())

    def absent(self):
        pair = self.discover()
        if pair:
            try:
                self.compute.delete_keypair(pair['name'])
            except ClientError as e:
                self.fail_json(
                    msg='Failed to delete keypair', msg_details=e.message)
            return dict(changed=True, msg='Keypair deleted')
        return dict(changed=False, msg='No such keypair')

    # General purpose SNF methods and properties
    @property
    def compute(self):
        if not self._compute:
            url, token = self.cloud.get('compute_url'), self.cloud.get('token')
            try:
                self._compute = CycladesClient(url, token)
            except ClientError as e:
                module.fail_json(
                    msg="Compute Client initialization failed",
                    msg_details=e.message)
        return self._compute


if __name__ == '__main__':
    module = SNFKeypair(
        argument_spec={
            'state': {'default': 'present', 'choices': ['present', 'absent']},
            'cloud': {'required': True, 'type': 'dict'},
            'public_key': {'reuired': False, 'type': 'str'},
            'name': {'required': False, 'type': 'str'},
        }
    )
    result = {
        'present': module.present,
        'absent': module.absent,
    }[module.params['state']]()
    module.exit_json(**result)
