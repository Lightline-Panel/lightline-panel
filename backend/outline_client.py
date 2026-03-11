import aiohttp
import os
import random
import string
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / '.env')
OUTLINE_MODE = os.environ.get('OUTLINE_MODE', 'mock')


class OutlineClient:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.mode = OUTLINE_MODE

    async def _request(self, method, path, **kwargs):
        if self.mode == 'mock':
            return await self._mock_request(method, path, **kwargs)
        headers = {'Authorization': f'Bearer {self.api_key}'}
        url = f'{self.api_url}/{path}'
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, ssl=False, **kwargs) as resp:
                if resp.content_type == 'application/json':
                    return await resp.json()
                return {'status': resp.status}

    async def _mock_request(self, method, path, **kwargs):
        if 'server' in path:
            return {'name': 'Mock Outline Server', 'serverId': 'mock-server', 'version': '1.8.1',
                    'metricsEnabled': True, 'createdTimestampMs': 1700000000000}
        if 'access-keys' in path and method == 'GET':
            return {'accessKeys': []}
        if 'access-keys' in path and method == 'POST':
            key_id = ''.join(random.choices(string.digits, k=4))
            host = self.api_url.split('//')[1].split(':')[0] if '//' in self.api_url else '127.0.0.1'
            name = kwargs.get('json', {}).get('name', 'User')
            access_url = f'ss://Y2hhY2hhMjAtaWV0Zi1wb2x5MTMwNTpwYXNz@{host}:8388/?outline=1#{name}'
            return {'id': key_id, 'accessUrl': access_url, 'name': name}
        if 'access-keys' in path and method in ('DELETE', 'PUT'):
            return {'status': 'ok'}
        if 'metrics' in path:
            return {'bytesTransferredByUserId': {str(i): random.randint(1000000, 5000000000) for i in range(10)}}
        return {}

    async def get_server_info(self):
        return await self._request('GET', 'server')

    async def get_access_keys(self):
        return await self._request('GET', 'access-keys')

    async def create_access_key(self, name=None):
        data = {'name': name} if name else {}
        return await self._request('POST', 'access-keys', json=data)

    async def delete_access_key(self, key_id):
        return await self._request('DELETE', f'access-keys/{key_id}')

    async def rename_access_key(self, key_id, name):
        return await self._request('PUT', f'access-keys/{key_id}/name', json={'name': name})

    async def set_data_limit(self, key_id, limit_bytes):
        return await self._request('PUT', f'access-keys/{key_id}/data-limit', json={'limit': {'bytes': limit_bytes}})

    async def get_metrics(self):
        return await self._request('GET', 'metrics/transfer')

    async def check_health(self):
        try:
            info = await self.get_server_info()
            return info is not None and 'name' in info
        except Exception:
            return False
