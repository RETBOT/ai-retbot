#!/usr/bin/env python
"""CLI para administración del sistema"""
import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone

from core.database import init_db, User, AuditLog, APIKey, async_session
from core.auth import hash_password, verify_password, create_access_token
from sqlalchemy import select
from core.config import settings


async def create_admin(args):
    """Crear usuario admin"""
    await init_db()
    
    async with async_session() as session:
        # Verificar si existe
        result = await session.execute(select(User).where(User.username == args.username))
        existing = result.scalar_one_or_none()
        
        if existing:
            # Actualizar password
            existing.password_hash = hash_password(args.password)
            existing.is_admin = True
            existing.is_active = True
            existing.password_changed_at = datetime.now(timezone.utc)
            existing.password_expires_at = datetime.now(timezone.utc) + timedelta(days=settings.PASSWORD_EXPIRE_DAYS)
            await session.commit()
            print(f"✅ Admin '{args.username}' actualizado")
        else:
            # Crear nuevo
            admin = User(
                username=args.username,
                password_hash=hash_password(args.password),
                is_admin=True,
                is_active=True,
                password_changed_at=datetime.now(timezone.utc),
                password_expires_at=datetime.now(timezone.utc) + timedelta(days=settings.PASSWORD_EXPIRE_DAYS)
            )
            session.add(admin)
            await session.commit()
            print(f"✅ Admin '{args.username}' creado")
        
        # Generar token
        result = await session.execute(select(User).where(User.username == args.username))
        user = result.scalar_one()
        token = create_access_token({"sub": user.id, "username": user.username})
        print(f"🎫 Token de acceso:")
        print(f"   {token}")


async def list_users(args):
    """Listar usuarios"""
    await init_db()
    
    async with async_session() as session:
        result = await session.execute(select(User).order_by(User.created_at.desc()))
        users = result.scalars().all()
        
        if not users:
            print("No hay usuarios")
            return
        
        print(f"\n👥 Usuarios ({len(users)}):\n")
        for u in users:
            status = "✅" if u.is_active else "❌"
            admin = " 👑" if u.is_admin else ""
            print(f"  {status} {u.username}{admin}")
            print(f"      ID: {u.id}")
            print(f"      Password expira: {u.password_expires_at}")
            print()


async def show_user(args):
    """Mostrar usuario específico"""
    await init_db()
    
    async with async_session() as session:
        if args.username:
            result = await session.execute(select(User).where(User.username == args.username))
        else:
            result = await session.execute(select(User).where(User.is_admin == True))
        
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"Usuario no encontrado")
            return
        
        print(f"\n👤 {user.username}")
        print(f"   ID: {user.id}")
        print(f"   Admin: {'Sí' if user.is_admin else 'No'}")
        print(f"   Activo: {'Sí' if user.is_active else 'No'}")
        print(f"   Password cambiada: {user.password_changed_at}")
        print(f"   Password expira: {user.password_expires_at}")
        print(f"   Creado: {user.created_at}")


async def login(args):
    """Hacer login y mostrar token"""
    await init_db()
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == args.username))
        user = result.scalar_one_or_none()
        
        if not user or not verify_password(args.password, user.password_hash):
            print("❌ Username o password incorrectos")
            return
        
        if not user.is_active:
            print("❌ Usuario desactivado")
            return
        
        token = create_access_token({"sub": user.id, "username": user.username})
        print(f"✅ Login exitoso")
        print(f"🎫 Token:")
        print(f"   {token}")


async def audit_logs(args):
    """Ver logs de auditoría"""
    await init_db()
    
    async with async_session() as session:
        result = await session.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(20)
        )
        logs = result.scalars().all()
        
        if not logs:
            print("No hay logs")
            return
        
        print(f"\n📋 Logs de auditoría:\n")
        for log in logs:
            print(f"  {log.created_at}: {log.action}")
            if log.details:
                print(f"     {log.details}")


async def create_api_key(args):
    """Crear API Key para un usuario"""
    import secrets
    import hashlib
    
    await init_db()
    
    async with async_session() as session:
        # Buscar usuario
        result = await session.execute(
            select(User).where(User.username == args.username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"❌ Usuario '{args.username}' no encontrado")
            return
        
        # Generar API key aleatoria
        # Formato: rb_<32 caracteres alphanumeric>
        random_part = secrets.token_urlsafe(32)
        api_key = f"rb_{random_part}"
        
        # Hashear la key para almacenar
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Crear registro en DB
        db_key = APIKey(
            user_id=user.id,
            name=args.name,
            key_hash=key_hash,
            permissions=args.permissions,
            is_active=True
        )
        session.add(db_key)
        await session.commit()
        
        print(f"✅ API Key creada exitosamente")
        print(f"\n📝 Detalles:")
        print(f"   Usuario: {user.username}")
        print(f"   Nombre: {args.name}")
        print(f"   Permisos: {args.permissions}")
        print(f"\n🔑 API Key (¡GUARDÁ ESTO! No se puede ver de nuevo):")
        print(f"   {api_key}")
        print(f"\n📋 Para usar con OpenCode, agregá este header:")
        print(f'   "X-API-Key": "{api_key}"')


async def list_api_keys(args):
    """Listar API Keys de un usuario"""
    await init_db()
    
    async with async_session() as session:
        # Buscar usuario
        result = await session.execute(
            select(User).where(User.username == args.username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"❌ Usuario '{args.username}' no encontrado")
            return
        
        # Buscar keys
        result = await session.execute(
            select(APIKey)
            .where(APIKey.user_id == user.id)
            .order_by(APIKey.created_at.desc())
        )
        keys = result.scalars().all()
        
        if not keys:
            print(f"No hay API keys para '{args.username}'")
            return
        
        print(f"\n🔑 API Keys de '{args.username}' ({len(keys)}):\n")
        for k in keys:
            status = "✅" if k.is_active else "❌"
            last_used = k.last_used_at.strftime("%Y-%m-%d %H:%M") if k.last_used_at else "Nunca"
            print(f"  {status} {k.name}")
            print(f"     ID: {k.id}")
            print(f"     Permisos: {k.permissions}")
            print(f"     Último uso: {last_used}")
            print(f"     Creada: {k.created_at.strftime('%Y-%m-%d %H:%M')}")
            print()


def main():
    parser = argparse.ArgumentParser(description="CLI de administración")
    subparsers = parser.add_subparsers(dest="command", help="Comandos")
    
    # create-admin
    p_create = subparsers.add_parser("create-admin", help="Crear admin")
    p_create.add_argument("--user", default="admin", help="Username")
    p_create.add_argument("--password", help="Password (si no se usa, pedir)")
    
    # list-users
    subparsers.add_parser("list-users", help="Listar usuarios")
    
    # user
    p_user = subparsers.add_parser("user", help="Ver usuario")
    p_user.add_argument("--username", help="Username (opcional)")
    
    # login
    p_login = subparsers.add_parser("login", help="Hacer login")
    p_login.add_argument("username", help="Username")
    p_login.add_argument("password", help="Password")
    
    # audit-logs
    subparsers.add_parser("audit-logs", help="Ver logs de auditoría")
    
    # create-api-key
    p_apikey = subparsers.add_parser("create-api-key", help="Crear API key para usuario")
    p_apikey.add_argument("--user", required=True, help="Username del usuario")
    p_apikey.add_argument("--name", required=True, help="Nombre descriptivo (ej: 'OpenCode Desktop')")
    p_apikey.add_argument("--permissions", default="chat", help="Permisos (default: chat)")
    
    # list-api-keys
    p_listkeys = subparsers.add_parser("list-api-keys", help="Listar API keys de un usuario")
    p_listkeys.add_argument("--user", required=True, help="Username del usuario")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "create-admin":
        password = args.password
        if not password:
            import getpass
            password = getpass.getpass("Password: ")
        asyncio.run(create_admin(args))
    elif args.command == "list-users":
        asyncio.run(list_users(args))
    elif args.command == "user":
        asyncio.run(show_user(args))
    elif args.command == "login":
        asyncio.run(login(args))
    elif args.command == "audit-logs":
        asyncio.run(audit_logs(args))
    elif args.command == "create-api-key":
        asyncio.run(create_api_key(args))
    elif args.command == "list-api-keys":
        asyncio.run(list_api_keys(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()