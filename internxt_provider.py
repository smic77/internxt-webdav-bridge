"""
Internxt Provider for asgi-webdav
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from asgi_webdav.constants import (
    DAVDepth,
    DAVPath,
    DAVResponseBodyGenerator,
    DAVResponseContentRange,
    DAVTime,
)
from asgi_webdav.property import DAVProperty, DAVPropertyBasicData
from asgi_webdav.exceptions import DAVExceptionProviderInitFailed
from asgi_webdav.helpers import generate_etag, guess_type
from asgi_webdav.provider.common import DAVProvider, DAVProviderFeature
from asgi_webdav.request import DAVRequest

logger = logging.getLogger(__name__)


class InternxtProvider(DAVProvider):
    """
    WebDAV provider for Internxt Drive
    Uses the internxt.py script to interact with Internxt API
    """
    type = "internxt"
    feature = DAVProviderFeature(
        content_range=False,  # Internxt doesn't support range requests
        home_dir=False,
    )

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        
        # Load credentials from file
        # Try to get from environment variable first, then from config
        import os
        credentials_file = os.environ.get("INTERXT_CREDENTIALS_FILE")
        
        if not credentials_file:
            # Try to get from kwargs (passed via config)
            credentials_file = kwargs.get("credentials_file")
        
        if not credentials_file:
            raise DAVExceptionProviderInitFailed(
                "InternxtProvider requires 'INTERXT_CREDENTIALS_FILE' environment variable or 'credentials_file' parameter"
            )
        
        try:
            with open(credentials_file, "r") as f:
                self.credentials = json.load(f)
        except Exception as e:
            raise DAVExceptionProviderInitFailed(
                f"Failed to load Internxt credentials from {credentials_file}: {e}"
            )
        
        # Import internxt module
        try:
            import internxt
            self.internxt = internxt
        except ImportError as e:
            raise DAVExceptionProviderInitFailed(
                f"Failed to import internxt module. Make sure internxt.py is in PYTHONPATH: {e}"
            )
        
        # Initialize client
        self.client = self.internxt.InternxtClient(
            self.credentials["token"],
            self.credentials.get("new_token")
        )
        
        logger.info(f"InternxtProvider initialized for user: {self.credentials.get('email')}")

    def __repr__(self) -> str:
        return f"internxt://{self.credentials.get('email', 'unknown')}"

    async def _resolve_path(self, path: DAVPath) -> tuple[str, str, bool]:
        """
        Resolve DAV path to Internxt UUID
        Returns: (uuid, name, is_folder)
        """
        # Convert DAVPath to string path
        path_str = "/" + "/".join(path.parts)
        
        try:
            uuid, name, is_folder = self.internxt._resolve_path(
                self.client,
                self.credentials,
                path_str
            )
            return uuid, name, is_folder
        except SystemExit:
            # Path doesn't exist
            return None, None, None

    async def _get_dav_property(
        self,
        request: DAVRequest,
        href_path: DAVPath,
        uuid: str,
        is_folder: bool,
        name: str = None
    ) -> DAVProperty:
        """Create DAVProperty object from Internxt resource"""
        if is_folder:
            basic_data = DAVPropertyBasicData(
                is_collection=True,
                display_name=name or href_path.name,
                creation_date=DAVTime(0),
                last_modified=DAVTime(0),
            )
        else:
            # Get file metadata
            meta = self.client.get(f"/files/{uuid}/meta")
            size = int(meta.get("size") or 0)
            
            content_type, content_encoding = guess_type(
                self.config,
                Path(meta.get("plainName") or meta.get("name", ""))
            )
            
            basic_data = DAVPropertyBasicData(
                is_collection=False,
                display_name=meta.get("plainName") or meta.get("name") or name or href_path.name,
                creation_date=DAVTime(0),
                last_modified=DAVTime(0),
                content_type=content_type or "application/octet-stream",
                content_charset=None,
                content_length=size,
                content_encoding=content_encoding,
            )
        
        dav_property = DAVProperty(
            href_path=href_path,
            is_collection=is_folder,
            basic_data=basic_data
        )
        
        return dav_property

    async def _do_propfind(self, request: DAVRequest) -> dict[DAVPath, DAVProperty]:
        """List files and folders"""
        dav_properties: dict[DAVPath, DAVProperty] = dict()
        
        # Resolve current path
        uuid, name, is_folder = await self._resolve_path(request.dist_src_path)
        
        if uuid is None:
            # Path doesn't exist
            return dav_properties
        
        # Add current resource
        dav_properties[request.src_path] = await self._get_dav_property(
            request, request.src_path, uuid, is_folder, name
        )
        
        # If it's a folder and depth > 0, list children
        if is_folder and request.depth != DAVDepth.ZERO:
            folders, files = self.internxt._list_folder(self.client, uuid)
            
            # Add folders
            for folder in folders:
                folder_name = folder.get("plainName") or folder.get("name", "")
                folder_uuid = folder.get("uuid") or folder.get("id")
                folder_path = request.src_path.add_child(folder_name)
                
                dav_properties[folder_path] = await self._get_dav_property(
                    request, folder_path, folder_uuid, True, folder_name
                )
            
            # Add files
            for file in files:
                file_name = file.get("plainName") or file.get("name", "")
                file_uuid = file.get("uuid") or file.get("id")
                file_path = request.src_path.add_child(file_name)
                
                dav_properties[file_path] = await self._get_dav_property(
                    request, file_path, file_uuid, False, file_name
                )
        
        return dav_properties

    async def _do_get(self, request: DAVRequest) -> tuple[
        int,
        DAVPropertyBasicData | None,
        DAVResponseBodyGenerator | None,
        DAVResponseContentRange | None,
    ]:
        """Download a file"""
        uuid, name, is_folder = await self._resolve_path(request.dist_src_path)
        
        if uuid is None:
            return 404, None, None, None
        
        if is_folder:
            # Return folder properties
            dav_property = await self._get_dav_property(
                request, request.src_path, uuid, True, name
            )
            return 200, dav_property.basic_data, None, None
        
        # Get file metadata
        meta = self.client.get(f"/files/{uuid}/meta")
        size = int(meta.get("size") or 0)
        
        content_type, content_encoding = guess_type(
            self.config,
            Path(meta.get("plainName") or meta.get("name", ""))
        )
        
        basic_data = DAVPropertyBasicData(
            is_collection=False,
            display_name=meta.get("plainName") or meta.get("name") or name,
            creation_date=DAVTime(0),
            last_modified=DAVTime(0),
            content_type=content_type or "application/octet-stream",
            content_charset=None,
            content_length=size,
            content_encoding=content_encoding,
        )
        
        # Download file content
        async def file_generator() -> DAVResponseBodyGenerator:
            file_id = meta.get("fileId") or meta.get("file_id")
            bucket_id = meta.get("bucket") or self.credentials["bucket"]
            
            net_headers = self.internxt._network_headers(
                self.credentials["bridge_user"],
                self.credentials["user_id"]
            )
            
            r = self.internxt.requests.get(
                f"{self.internxt.NETWORK_API}/buckets/{bucket_id}/files/{file_id}/info",
                headers={**net_headers, "x-api-version": "2"},
            )
            
            if not r.ok:
                logger.error(f"Failed to get file info: {r.status_code}")
                return
            
            info = r.json()
            index_hex = info.get("index")
            shards = info.get("shards", [])
            
            index_bytes = bytes.fromhex(index_hex)
            iv = index_bytes[:16]
            file_key = self.internxt._derive_file_key(
                self.credentials["mnemonic"],
                bucket_id,
                index_bytes
            )
            
            # Download and decrypt
            shards_sorted = sorted(shards, key=lambda s: s.get("index", 0))
            encrypted_chunks = []
            
            for shard in shards_sorted:
                shard_url = shard.get("url") or shard.get("farmer", {}).get("address")
                if not shard_url:
                    continue
                
                resp = self.internxt.requests.get(shard_url)
                if resp.ok:
                    encrypted_chunks.append(resp.content)
            
            encrypted = b"".join(encrypted_chunks)
            decrypted = self.internxt._aes256ctr_decrypt(encrypted, file_key, iv)
            
            # Yield in chunks
            chunk_size = 65536
            for i in range(0, len(decrypted), chunk_size):
                yield decrypted[i:i+chunk_size], (i + chunk_size < len(decrypted))
        
        return 200, basic_data, file_generator(), None

    async def _do_put(self, request: DAVRequest) -> int:
        """Upload a file"""
        # Check parent folder exists
        parent_path = DAVPath("/" + "/".join(request.dist_src_path.parts[:-1]))
        parent_uuid, _, parent_is_folder = await self._resolve_path(parent_path)
        
        if parent_uuid is None or not parent_is_folder:
            return 409
        
        # Collect request body
        chunks = []
        more_body = True
        while more_body:
            request_data = await request.receive()
            more_body = request_data.get("more_body", False)
            data = request_data.get("body", b"")
            chunks.append(data)
        
        content = b"".join(chunks)
        
        # Write to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        
        # Rename to correct filename
        file_name = request.dist_src_path.parts[-1]
        correct_path = tmp_path.parent / file_name
        tmp_path.rename(correct_path)
        
        try:
            # Upload using internxt
            self.internxt._upload_single_file(
                self.client,
                correct_path,
                parent_uuid,
                self.credentials["mnemonic"],
                self.credentials["bucket"],
                self.credentials["bridge_user"],
                self.credentials["user_id"],
            )
            return 201
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return 500
        finally:
            # Cleanup
            correct_path.unlink(missing_ok=True)

    async def _do_mkcol(self, request: DAVRequest) -> int:
        """Create a folder"""
        # Check parent exists
        parent_path = DAVPath("/" + "/".join(request.dist_src_path.parts[:-1]))
        parent_uuid, _, parent_is_folder = await self._resolve_path(parent_path)
        
        if parent_uuid is None or not parent_is_folder:
            return 409
        
        folder_name = request.dist_src_path.parts[-1]
        
        try:
            # Get parent metadata
            parent_meta = self.client.get(f"/folders/{parent_uuid}/meta")
            parent_id = parent_meta.get("id")
            
            # Create folder
            self.client.post("/folders", json={
                "name": folder_name,
                "plainName": folder_name,
                "parentId": parent_id,
                "parentFolderUuid": parent_uuid,
            })
            
            return 201
        except Exception as e:
            logger.error(f"MKCOL failed: {e}")
            return 500

    async def _do_delete(self, request: DAVRequest) -> int:
        """Delete a file or folder"""
        uuid, name, is_folder = await self._resolve_path(request.dist_src_path)
        
        if uuid is None:
            return 404
        
        try:
            if is_folder:
                # Delete folder
                self.client.delete(f"/folders/{uuid}")
            else:
                # Delete file
                self.client.delete(f"/files/{uuid}")
            
            return 204
        except Exception as e:
            logger.error(f"DELETE failed: {e}")
            return 500

    async def _do_proppatch(self, request: DAVRequest) -> int:
        """Update properties - not supported by Internxt"""
        return 207  # Return success but do nothing

    async def _do_copy(self, request: DAVRequest) -> int:
        """Copy - not supported by Internxt"""
        return 501  # Not Implemented

    async def _do_move(self, request: DAVRequest) -> int:
        """Move - not supported by Internxt"""
        return 501  # Not Implemented
