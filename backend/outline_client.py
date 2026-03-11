import aiohttp
import os
import random
import string
import logging
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / '.env')
OUTLINE_MODE = os.environ.get('OUTLINE_MODE', 'mock')
logger = logging.getLogger(__name__)


class OutlineClient:
    """Client that connects to either a direct Outline Server API or a Lightline Node agent.

    Direct Outline: api_url = https://ip:port/secret, api_key is unused
    Lightline Node: api_url = https://ip:port, api_key = node token (Bearer auth)

    Auto-detection: if the api_url path has a secret suffix (Outline style), use direct mode.
    Otherwise, treat it as a lightline-node agent.
    """

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.mode = OUTLINE_MODE

        # Detect connection type:
        # Outline URLs have a secret path like https://ip:port/AbCdEfGh
        # Lightline Node URLs are just https://ip:port
        from urllib.parse import urlparse
        parsed = urlparse(self.api_url)
        path = parsed.path.strip('/')
        self.is_lightline_node = (not path) or (path and len(path) < 4)

    async def _request(self, method, path, **kwargs):
        if self.mode == 'mock':
            return await self._mock_request(method, path, **kwargs)
        headers = {}
        if self.is_lightline_node:
            headers['Authorization'] = f'Bearer {self.api_key}'
        url = f'{self.api_url}/{path}'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method, url, headers=headers, ssl=False,
                    timeout=aiohttp.ClientTimeout(total=15), **kwargs
                ) as resp:
                    if resp.content_type == 'application/json':
                        return await resp.json()
                    return {'status': resp.status}
        except Exception as e:
            logger.error(f"Request error: {method} {url} — {e}")
            raise

    async def _mock_request(self, method, path, **kwargs):
        if 'server' in path:
            return {'name': 'Mock Outline Server', 'serverId': 'mock-server', 'version': '1.8.1',
                    'metricsEnabled': True, 'createdTimestampMs': 1700000000000}
        if path in ('access-keys', 'keys') and method == 'GET':
            return {'accessKeys': []}
        if path in ('access-keys', 'keys') and method == 'POST':
            key_id = ''.join(random.choices(string.digits, k=4))
            host = self.api_url.split('//')[1].split(':')[0] if '//' in self.api_url else '127.0.0.1'
            name = kwargs.get('json', {}).get('name', 'User')
            access_url = f'ss://Y2hhY2hhMjAtaWV0Zi1wb2x5MTMwNTpwYXNz@{host}:8388/?outline=1#{name}'
            return {'id': key_id, 'accessUrl': access_url, 'name': name}
        if ('access-keys' in path or 'keys' in path) and method in ('DELETE', 'PUT'):
            return {'status': 'ok'}
        if 'metrics' in path:
            return {'bytesTransferredByUserId': {str(i): random.randint(1000000, 5000000000) for i in range(10)}}
        return {}

    async def get_server_info(self):
        return await self._request('GET', 'server')

    async def get_access_keys(self):
        path = 'keys' if self.is_lightline_node else 'access-keys'
        return await self._request('GET', path)

    async def create_access_key(self, name=None):
        path = 'keys' if self.is_lightline_node else 'access-keys'
        data = {'name': name} if name else {}
        return await self._request('POST', path, json=data)

    async def delete_access_key(self, key_id):
        path = f'keys/{key_id}' if self.is_lightline_node else f'access-keys/{key_id}'
        return await self._request('DELETE', path)

    async def rename_access_key(self, key_id, name):
        path = f'keys/{key_id}/name' if self.is_lightline_node else f'access-keys/{key_id}/name'
        return await self._request('PUT', path, json={'name': name})

    async def set_data_limit(self, key_id, limit_bytes):
        if self.is_lightline_node:
            return await self._request('PUT', f'keys/{key_id}/data-limit',
                                       json={'limit_bytes': limit_bytes})
        return await self._request('PUT', f'access-keys/{key_id}/data-limit',
                                   json={'limit': {'bytes': limit_bytes}})

    async def get_metrics(self):
        return await self._request('GET', 'metrics')

    async def check_health(self):
        try:
            if self.is_lightline_node:
                result = await self._request('GET', 'health')
                return result.get('healthy', False)
            info = await self.get_server_info()
            return info is not None and 'name' in info
        except Exception:
            return False
