# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
import unittest
from services.asset_vault.vault_service import AssetVaultService

class TestAssetVault(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.vault = AssetVaultService(storage_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_store_and_retrieve_asset(self):
        raw_content = b"Creative Master Visual Deliverable Vector SVG Data"
        tenant_id = "tenant-creative-01"

        record = self.vault.store_asset(raw_content, tenant_id=tenant_id, metadata={"filename": "logo.svg"})
        self.assertIn("object_id", record)
        self.assertEqual(record["size_bytes"], len(raw_content))

        decrypted, meta = self.vault.retrieve_asset(record["object_id"], requesting_tenant_id=tenant_id)
        self.assertEqual(decrypted, raw_content)
        self.assertEqual(meta["sha256"], record["sha256"])

    def test_cross_tenant_access_blocked(self):
        raw_content = b"Confidential Corporate IP"
        record = self.vault.store_asset(raw_content, tenant_id="tenant-alpha")

        with self.assertRaises(PermissionError):
            self.vault.retrieve_asset(record["object_id"], requesting_tenant_id="tenant-bravo")

    def test_tamper_detection(self):
        raw_content = b"Signed Legal Deliverable Package"
        record = self.vault.store_asset(raw_content, tenant_id="tenant-alpha")

        # Corrupt the encrypted payload on disk
        obj_path = os.path.join(self.test_dir, f"{record['object_id']}.enc")
        with open(obj_path, 'r+b') as f:
            f.seek(5)
            f.write(b"TAMPER")

        with self.assertRaises(ValueError):
            self.vault.retrieve_asset(record["object_id"], requesting_tenant_id="tenant-alpha")

if __name__ == '__main__':
    unittest.main()
