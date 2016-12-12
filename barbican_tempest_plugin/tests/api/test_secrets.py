# Copyright 2016 SAP SE
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import base64
from datetime import datetime
from datetime import timedelta
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from barbican_tempest_plugin.tests.api import base


class SecretsTest(base.BaseKeyManagerTest):
    """Secrets API tests."""
    def test_create_delete_empty_secret(self):
        sec = self.create_secret()
        uuid = base._get_uuid(sec['secret_ref'])
        self.delete_secret(uuid)

    def test_create_delete_symmetric_key(self):
        password = b"password"
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt,
            iterations=1000, backend=default_backend()
        )
        key = base64.b64encode(kdf.derive(password))
        expire_time = (datetime.utcnow() + timedelta(days=5))
        sec = self.create_secret(
            expiration=expire_time.isoformat(), algorithm="aes",
            bit_length=256, mode="cbc", payload=key,
            payload_content_type="application/octet-stream",
            payload_content_encoding="base64"
        )
        uuid = base._get_uuid(sec['secret_ref'])
        self.delete_secret(uuid)
