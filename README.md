# Kamaki Ansible Role

This is an ansible role to use kamaki[1] with Synnefo[2]-based clouds, e.g. ~okeanos [3] or okeanos-knossos [4]. An `examples/` directory with a sample playbook and requirements file can be used as a guide.

To install the role, make sure you have `kamaki` installed (see [1]), e.g.:  
```
$ pip install git+https://github.com/grnet/kamaki.git
```  
  
 To install the `kamaki-ansible-role`, use `examles/requirements.yml` file. We suggest you copy the content of this file to your project `requirements.tml` file:
```
$ ansible-galaxy -r requirements.yml
```

To use the role, create a playbook similar to `examples/playbook.yml`, or like the following:
```
tasks:
- name: Test VM creation
  hosts: localhost
  tasks:
    - import_role:
        name: kamaki-ansibe-role
    - name: Authenticate cloud
      cloud:
        ca_certs='/etc/ssl/certs/ca-certificates.crt'
        url='https://astakos.okeanos-knossos.grnet.gr/identity/v2.0'
        token='MY-SYNNEFO-TOKEN'
        project_id='MY-PROJECT'
```

The file `examples/playbook.yml` contains examples of all the operations available in the role.

# List of operations

## cloud
Authenticate against the cloud, with the user token, ca_certificates and project id. For more information on project_id, token and url, see [2]. The ca_certs is needed for secure connections with the cloud. Use your systems certificates file e.g.,
```
*Debian / Ubuntu / Gentoo / Arch*
`/etc/ssl/certs/ca-certificates.crt`

*Fedora / RedHat*
`/etc/pki/tls/certs/ca-bundle.crt`

*OpenSuse*
`/etc/ssl/ca-bundle.pem`
```

Example role:
```
    - name: Authenticate cloud
      cloud:
        ca_certs='/etc/ssl/certs/ca-certificates.crt'
        url='https://astakos.okeanos-knossos.grnet.gr/identity/v2.0'
        token='MY-SYNNEFO-TOKEN'
        project_id='MY-PROJECT'
      register: cloud
```

## keypair
Create or upload a Public-Private Key pair on the cloud, using a name as reference. There are two operations disguised as one:
- If the name does not exist, it will be created.
- If no name is given, a key pair will be generated.

If you are using keypair to create a new key, make sure to save the private key on the first run. The private key is not stored anywhere in the cloud, it is the users responsibility to keep and use it. Check the example bellow:
```
    - name: Create PPK
      keypair:
        cloud={{ cloud }}
        name='My keypair'
      register: ppk
    - name: Save private key
      copy:
        # Only if this is a new key
        content={{ ppk.keypair.private_key }}
        dest=/tmp/my_private.key
      register: saved_key
```

To erase the keypair from the cloud:
```
    - name: Delete keypair
      keypair:
        state=absent
        cloud={{ cloud }}
        name={{ ppk.keypair.name }}
      register: ppk_deleted
```

Note that, if a VM is created with a keypair, the public key will remain in the VM even if the keypair is deleted. Post-creation VM contents are users responsibility.

## network
Create a private network on the cloud. This is an internal network with no external access built in. Private networks can have an IPv4 range (private IPs) and DHCP. Connect your VMs in a later step.
```
    - name: Create private network
      network:
        cloud={{ cloud }}
        name='my temp net'
        dhcp=True
        cidr='192.168.0.0/24'
      register: pnet
```

To destroy the private network:
```
    - name: Destroy private network
      network:
        state=absent
        cloud={{ cloud }}
        id={{ pnet.network.id }}
      register: pnet_deleted
```

## public_ip
Create an IPv4 visible from the outside world. If you know you have the right to use a specific free IP, you can use the `address` field to get it, otherwise the system will reserve another IP for you.
```
    - name: Create IP
      public_ip:
        cloud={{ cloud }}
        # address='83.212.73.217'
      register: ip
```

To free ("unreserve") the IP:
```
    - name: Free IP
      public_ip:
        state=absent
        cloud={{ cloud }}
        id={{ ip.ip.id }}
      register: ip_deleted
```

## server
Create and manage VMs. In order to attach VMs to networks, keypairs etc., you need to create these artifacts at a previous step.
```
    - name: Create VM
      server:
        cloud={{ cloud }}
        name='My temp VM'
        flavor_id=260
        image_id='051669a1-835a-4e01-995e-1d21c74839c7'
        public_ip={{ ip }}
        network={{ pnet }}
        keypair={{ ppk }}
      register: vm
```

To destroy the VM:
```
    - name: Destroy VM
      server:
        state=absent
        cloud={{ cloud }}
        id={{ vm.server.id }}
      register: vm_deleted
```

# References

[1] https://www.synnefo.org/docs/kamaki/latest/
[2] https://www.synnefo.org
[3] https://okeanos.grnet.gr
[4] https://okeanos-knossos.grnet.gr