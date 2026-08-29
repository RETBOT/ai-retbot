#!/usr/bin/env python3
"""Script rápido para ver API Keys en la BD"""
import asyncio
from core.database import async_session, APIKey
from core.auth import mask_api_key_hash, key_storage_format
from sqlalchemy import select

async def main():
    async with async_session() as session:
        result = await session.execute(select(APIKey))
        keys = result.scalars().all()
        
        print(f"\n📋 Total API Keys: {len(keys)}\n")
        
        for key in keys:
            status = "✅" if key.is_active else "❌"
            print(f"{status} ID: {key.id}")
            print(f"   Name: {key.name or 'Sin nombre'}")
            print(f"   Hash (enmascarado): {mask_api_key_hash(key.key_hash)}")
            print(f"   Formato: {key_storage_format(key.key_hash)}")
            print(f"   User ID: {key.user_id}")
            print()

if __name__ == "__main__":
    asyncio.run(main())
