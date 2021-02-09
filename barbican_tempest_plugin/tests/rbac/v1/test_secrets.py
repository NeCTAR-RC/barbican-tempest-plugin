# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import abc
import base64
from datetime import datetime
from datetime import timedelta
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from tempest import config
from tempest.lib import exceptions

from barbican_tempest_plugin.tests.rbac.v1 import base as rbac_base

CONF = config.CONF


def create_aes_key():
    password = b"password"
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt,
        iterations=1000, backend=default_backend()
    )
    return base64.b64encode(kdf.derive(password))


class BarbicanV1RbacSecretsBase(rbac_base.BarbicanV1RbacBase,
                                metaclass=abc.ABCMeta):

    @classmethod
    def setup_clients(cls):
        super().setup_clients()
        cls.client = cls.secret_client

    def create_empty_secret_admin(self, secret_name):
        """add empty secret as admin user """
        return self.do_request(
            'create_secret', client=self.admin_secret_client,
            expected_status=201, cleanup='secret', name=secret_name)

    def create_aes_secret_admin(self, secret_name):
        key = create_aes_key()
        expire_time = (datetime.utcnow() + timedelta(days=5))
        return key, self.do_request(
            'create_secret', client=self.admin_secret_client,
            expected_status=201, cleanup="secret",
            expiration=expire_time.isoformat(), algorithm="aes",
            bit_length=256, mode="cbc", payload=key,
            payload_content_type="application/octet-stream",
            payload_content_encoding="base64",
            name=secret_name
        )

    @abc.abstractmethod
    def test_create_secret(self):
        """Test add_secret policy.

        Testing: POST /v1/secrets
        This test must check:
          * whether the persona can create an empty secret
          * whether the persona can create a secret with a symmetric key
        """
        pass

    @abc.abstractmethod
    def test_list_secrets(self):
        """Test get_secrets policy.

        Testing: GET /v1/secrets
        This test must check:
          * whether the persona can list secrets within their project
        """
        pass

    @abc.abstractmethod
    def test_delete_secret(self):
        """Test deleting a secret.

        Testing: DEL /v1/secrets/{secret_id}
        This test must check:
          * whether the persona can delete a secret in their project
        """
        pass

    @abc.abstractmethod
    def test_get_secret(self):
        """Test get_secret policy.

        Testing: GET /v1/secrets/{secret_id}
        This test must check:
          * whether the persona can get a specific secret within their project
        """
        pass

    @abc.abstractmethod
    def test_get_secret_payload(self):
        """Test get_secret payload policy.

        Testing: GET /v1/secrets/{secret_id}/payload
        This test must check:
          * whether the persona can get a secret payload
        """
        pass

    @abc.abstractmethod
    def test_put_secret_payload(self):
        """Test put_secret policy.

        Testing: PUT /v1/secrets/{secret_id}
        This test must check:
          * whether the persona can add a paylod to an empty secret
        """
        pass


class ProjectMemberTests(BarbicanV1RbacSecretsBase):
    credentials = ['project_member', 'project_admin']

    def test_create_secret(self):
        """Test add_secret policy."""
        self.do_request('create_secret', expected_status=201, cleanup='secret')

        key = create_aes_key()
        expire_time = (datetime.utcnow() + timedelta(days=5))
        self.do_request(
            'create_secret', expected_status=201, cleanup="secret",
            expiration=expire_time.isoformat(), algorithm="aes",
            bit_length=256, mode="cbc", payload=key,
            payload_content_type="application/octet-stream",
            payload_content_encoding="base64"
        )

    def test_list_secrets(self):
        """Test get_secrets policy."""
        # create two secrets
        self.create_empty_secret_admin('secret_1')
        self.create_empty_secret_admin('secret_2')

        # list secrets with name secret_1
        resp = self.do_request('list_secrets', name='secret_1')
        secrets = resp['secrets']
        self.assertEqual('secret_1', secrets[0]['name'])

        # list secrets with name secret_2
        resp = self.do_request('list_secrets', name='secret_2')
        secrets = resp['secrets']
        self.assertEqual('secret_2', secrets[0]['name'])

        # list all secrets
        resp = self.do_request('list_secrets')
        secrets = resp['secrets']
        self.assertEqual(len(secrets), 2)

    def test_delete_secret(self):
        """Test delete_secrets policy."""
        sec = self.create_empty_secret_admin('secret_1')
        uuid = rbac_base._get_uuid(sec['secret_ref'])
        self.do_request('delete_secret', secret_id=uuid)
        self.delete_cleanup('secret', uuid)

    def test_get_secret(self):
        """Test get_secret policy."""
        sec = self.create_empty_secret_admin('secret_1')
        uuid = rbac_base._get_uuid(sec['secret_ref'])
        resp = self.do_request('get_secret_metadata', secret_id=uuid)
        self.assertEqual(uuid, rbac_base._get_uuid(resp['secret_ref']))

    def test_get_secret_payload(self):
        """Test get_secret payload policy."""
        key, sec = self.create_aes_secret_admin('secret_1')
        uuid = rbac_base._get_uuid(sec['secret_ref'])

        # Retrieve the payload
        payload = self.do_request('get_secret_payload', secret_id=uuid)
        self.assertEqual(key, base64.b64encode(payload))

    def test_put_secret_payload(self):
        """Test put_secret policy."""
        sec = self.create_empty_secret_admin('secret_1')
        uuid = rbac_base._get_uuid(sec['secret_ref'])

        key = create_aes_key()

        # Associate the payload with the created secret
        self.do_request('put_secret_payload', secret_id=uuid, payload=key)

        # Retrieve the payload
        payload = self.do_request('get_secret_payload', secret_id=uuid)
        self.assertEqual(key, base64.b64encode(payload))


class ProjectAdminTests(ProjectMemberTests):
    credentials = ['project_admin', 'project_admin']


class ProjectReaderTests(BarbicanV1RbacSecretsBase):
    credentials = ['project_reader', 'project_admin']

    def test_create_secret(self):
        """Test add_secret policy."""
        self.do_request(
            'create_secret', expected_status=exceptions.Forbidden,
            cleanup='secret')

        key = create_aes_key()
        expire_time = (datetime.utcnow() + timedelta(days=5))
        self.do_request(
            'create_secret', expected_status=exceptions.Forbidden,
            cleanup="secret",
            expiration=expire_time.isoformat(), algorithm="aes",
            bit_length=256, mode="cbc", payload=key,
            payload_content_type="application/octet-stream",
            payload_content_encoding="base64"
        )

    def test_list_secrets(self):
        """Test get_secrets policy."""
        # create two secrets
        self.create_empty_secret_admin('secret_1')
        self.create_empty_secret_admin('secret_2')

        # list secrets with name secret_1
        self.do_request(
            'list_secrets', expected_status=exceptions.Forbidden,
            name='secret_1'
        )

        # list secrets with name secret_2
        self.do_request(
            'list_secrets', expected_status=exceptions.Forbidden,
            name='secret_2'
        )

        # list all secrets
        self.do_request(
            'list_secrets', expected_status=exceptions.Forbidden
        )

    def test_delete_secret(self):
        """Test delete_secrets policy."""
        sec = self.create_empty_secret_admin('secret_1')
        uuid = rbac_base._get_uuid(sec['secret_ref'])
        self.do_request(
            'delete_secret', expected_status=exceptions.Forbidden,
            secret_id=uuid
        )

    def test_get_secret(self):
        """Test get_secret policy."""
        sec = self.create_empty_secret_admin('secret_1')
        uuid = rbac_base._get_uuid(sec['secret_ref'])
        self.do_request(
            'get_secret_metadata', expected_status=exceptions.Forbidden,
            secret_id=uuid
        )

    def test_get_secret_payload(self):
        """Test get_secret payload policy."""
        key, sec = self.create_aes_secret_admin('secret_1')
        uuid = rbac_base._get_uuid(sec['secret_ref'])

        # Retrieve the payload
        self.do_request(
            'get_secret_payload', expected_status=exceptions.Forbidden,
            secret_id=uuid
        )

    def test_put_secret_payload(self):
        """Test put_secret policy."""
        sec = self.create_empty_secret_admin('secret_1')
        uuid = rbac_base._get_uuid(sec['secret_ref'])

        key = create_aes_key()

        # Associate the payload with the created secret
        self.do_request(
            'put_secret_payload', expected_status=exceptions.Forbidden,
            secret_id=uuid, payload=key
        )


class SystemAdminTests(BarbicanV1RbacSecretsBase):
    credentials = ['system_admin', 'project_admin']

    def test_create_secret(self):
        pass

    def test_list_secrets(self):
        pass

    def test_delete_secret(self):
        pass

    def test_get_secret(self):
        pass

    def test_get_secret_payload(self):
        pass

    def test_put_secret_payload(self):
        pass


class SystemMemberTests(BarbicanV1RbacSecretsBase):
    credentials = ['system_member', 'project_admin']

    def test_create_secret(self):
        pass

    def test_list_secrets(self):
        pass

    def test_delete_secret(self):
        pass

    def test_get_secret(self):
        pass

    def test_get_secret_payload(self):
        pass

    def test_put_secret_payload(self):
        pass


class SystemReaderTests(BarbicanV1RbacSecretsBase):
    credentials = ['system_reader', 'project_admin']

    def test_create_secret(self):
        pass

    def test_list_secrets(self):
        pass

    def test_delete_secret(self):
        pass

    def test_get_secret(self):
        pass

    def test_get_secret_payload(self):
        pass

    def test_put_secret_payload(self):
        pass
