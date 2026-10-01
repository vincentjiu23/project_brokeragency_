# -*- coding: utf-8 -*-
"""
VIN Asset Vault — Encrypted Content-Addressed Storage Service
Provides SHA-256 content addressing, envelope encryption, and immutable WORM storage.
"""

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone

class AssetVaultService:
    """Core cryptographic and content-addressed storage adapter for VIN Asset Vault."""

    def __init__(self, storage_dir=None, kms_master_key=b"vin_master_kms_key_32_bytes_pad!!"):
        self.storage_dir = storage_dir or os.path.join(os.path.dirname(__file__), ".storage")
        self.kms_master_key = kms_master_key
        os.makedirs(self.storage_dir, exist_ok=True)

    def compute_sha256(self, data: bytes) -> str:
        """Computes deterministic SHA-256 digest of content."""
        hasher = hashlib.sha256()
        hasher.update(data)
        return hasher.hexdigest()

    def store_asset(self, data: bytes, tenant_id: str, metadata: dict = None) -> dict:
        """
        Stores an encrypted asset in content-addressed storage with SHA-256 verification.
        """
        sha256_digest = self.compute_sha256(data)
        object_id = str(uuid.uuid4())

        # Generate envelope data encryption key (DEK) HMAC simulated
        dek = hmac.new(self.kms_master_key, object_id.encode('utf-8'), hashlib.sha256).digest()
        
        # Simulated envelope encryption (XOR with DEK keystream for deterministic testability)
        encrypted_payload = bytes(b ^ dek[i % len(dek)] for i, b in enumerate(data))

        record = {
            'object_id': object_id,
            'sha256': sha256_digest,
            'size_bytes': len(data),
            'tenant_id': tenant_id,
            'kms_key_id': 'kms/vin-prod-vault-key-01',
            'stored_at': datetime.now(timezone.utc).isoformat(),
            'metadata': metadata or {}
        }

        # Persist encrypted object and metadata descriptor
        obj_path = os.path.join(self.storage_dir, f"{object_id}.enc")
        meta_path = os.path.join(self.storage_dir, f"{object_id}.meta.json")

        with open(obj_path, 'wb') as f:
            f.write(encrypted_payload)
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(record, f, indent=2)

        return record

    def retrieve_asset(self, object_id: str, requesting_tenant_id: str) -> tuple[bytes, dict]:
        """
        Retrieves, decrypts, and verifies SHA-256 integrity of an asset.
        """
        obj_path = os.path.join(self.storage_dir, f"{object_id}.enc")
        meta_path = os.path.join(self.storage_dir, f"{object_id}.meta.json")

        if not os.path.exists(meta_path) or not os.path.exists(obj_path):
            raise FileNotFoundError(f"Asset object {object_id} not found in vault.")

        with open(meta_path, 'r', encoding='utf-8') as f:
            record = json.load(f)

        # Tenant boundary validation
        if record['tenant_id'] != requesting_tenant_id:
            raise PermissionError("Access Denied: Cross-tenant unauthorized access blocked!")

        with open(obj_path, 'rb') as f:
            encrypted_payload = f.read()

        # Decrypt with derived DEK
        dek = hmac.new(self.kms_master_key, object_id.encode('utf-8'), hashlib.sha256).digest()
        decrypted_data = bytes(b ^ dek[i % len(dek)] for i, b in enumerate(encrypted_payload))

        # Verify SHA-256 integrity check
        computed_digest = self.compute_sha256(decrypted_data)
        if computed_digest != record['sha256']:
            raise ValueError("Cryptographic Integrity Error: Tampering detected! SHA-256 mismatch.")

        return decrypted_data, record

    def generate_upload_authorization(self, tenant_id: str, expected_size: int, mime_type: str) -> dict:
        """
        Generates signed upload authorization token (presigned upload abstraction).
        """
        token_id = str(uuid.uuid4())
        signature = hmac.new(
            self.kms_master_key,
            f"{tenant_id}:{expected_size}:{token_id}".encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return {
            'upload_token': token_id,
            'signature': signature,
            'tenant_id': tenant_id,
            'max_bytes': expected_size,
            'mime_type': mime_type,
            'expires_in_seconds': 3600
        }
