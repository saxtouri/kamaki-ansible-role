#!/usr/bin/python
# Copyright 2018 Stavros Sachtouris <saxtouri@grnet.gr>
import re
from kamaki.clients import ClientError
from kamaki.clients.astakos import AstakosClient
from kamaki.clients.utils import https
from ansible.module_utils.basic import AnsibleModule


class SNFCloud(AnsibleModule):
    """Synnefo Cloud parent class
       Performs user authentication, kamaki SSL, project id check
       Designed to be imprted by other classes (e.g. compute, storage, etc.)
    """
    _astakos = None

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
            msg = 'Error with project id "{}"'.format(self.project_id)
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
