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
        self._handle_ssl()
        self._check_project_id()

    # General purpose SNF methods and properties
    def _handle_ssl(self):
        ca_certs = self.params.get('ca_certs')
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
        project_id = self.params.get('project_id')
        if project_id:
            try:
                project = self.astakos.get_project(project_id)
            except ClientError as e:
                msg = 'Error with project id "{}"'.format(project_id)
                self.fail_json(msg=msg, msg_details=e.message)
            if project['state'] != 'active':
                msg = 'Project {id} is inactive (state: {state})'
                self.fail_json(msg=msg.format(
                    pname=project['name'], state=project['state']))
        return project_id

    @property
    def astakos(self):
        if not self._astakos:
            try:
                self._astakos = AstakosClient(
                    self.params.get('cloud_url'),
                    self.params.get('cloud_token'))
            except ClientError as e:
                self.fail_json(
                    msg="Astakos Client initialization failed",
                    msg_details=e.message)
        return self._astakos

    def get_api_url(self, api):
        try:
            return self.astakos.get_endpoint_url(api)
        except ClientError as e:
            module.fail_json(
                msg="{} api endpoint retrieval failed".format(api),
                msg_details=e.message)

    def present(self):
        cloud = {key: module.params.get(key) for key in (
            'cloud_url', 'cloud_token', 'project_id', 'ca_certs')}
        cloud['compute_url'] = self.get_api_url('compute')
        cloud['network_url'] = self.get_api_url('network')
        return dict(changed=True, msg=cloud)


if __name__ == '__main__':
    module = SNFCloud(
        argument_spec={
            'ca_certs': {'required': False, 'type': 'str'},
            'cloud_url': {'required': True, 'type': 'str'},
            'cloud_token': {'required': True, 'type': 'str'},
            'project_id': {'required': False, 'type': 'str'},
        },
        required_if=(('state', 'connected', ('vm_id', )), )
    )
    module.exit_json(**module.present())
