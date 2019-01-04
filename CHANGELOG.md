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


Version 0.2
-----------
There are five modules, exchanging information through playbook. Check the
"example.yml" for an example.

Here are the modules:
- cloud: authenticate cloud credentials. Result used by every other module
	as input.
- server: create or destroy a VM.
- network: create or destroy a private network. Also, connect or disconnect
	VMs on an existing network.
- public_ip: create, reserve or destroy a public ip v4. Also, connect or
	disconnect it to a VM. A reserved IP is not destroyed with this module,
	it is only freed (to be used later, probably). Can be used to move IPs
	between VMs.
- keypair: Public/Private ssh key pair to be used with VMs. It can discover
	existing keys by name or public key, or create a new pair. In the later
	case, you may need to copy the private key to a file. Private keys are
	generated only once, so make sure to get it while it is still there.
	See "example.yml" for more details.

Version 0.3
-----------
The "kamaki-ansible-role" is now ready to be imported. Check the directory "example", which showcases how it can be used:
- Install the role with `ansible-galaxy -r requirements.yml`
- Edit and run the playbook with `ansible-playbook playbook.yml`
