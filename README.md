# kamaki-ansible-role
Ansible role and module to provision and manage compute resources on Synnefo
clouds, based on the kamaki client.

Kamaki is the de-facto client for Synnefo IaaS. For more information:
- https://www.synnefo.org/docs/kamaki/latest
- https://www.synnefo.org

The Synnefo API is almost compatible with the OpenStack API, but not completely.
In many cases, useful and required features of Synnefo are impossible to use
with an OpenStack client. The best way to fully access the Synnefo API is the
kamaki client.

Version 0.1
-----------
Expose basic operations (create, delete, query) for Synnefo compute resources:
VMs, public IPs, private networks, ssh keys and volumes.
