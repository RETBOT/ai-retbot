"""
Tool Executor - Ejecución segura de tools

Implementa la ejecución de cada tool con validaciones de seguridad:
- Path traversal protection
- Command whitelist
- File size limits
- Timeout handling
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Resultado de la ejecución de una tool"""
    success: bool
    content: str
    error: Optional[str] = None


class ToolExecutor:
    """
    Ejecutor de tools con validaciones de seguridad.
    
    Cada tool implementa su propia lógica de ejecución y validación.
    El executor asegura que todas las operaciones sean seguras.
    """
    
    # Comandos permitidos (whitelist) para execute_command
    ALLOWED_COMMANDS = {
        # File operations
        'ls', 'dir', 'cat', 'type', 'head', 'tail', 'wc', 'find',
        # Navigation
        'pwd', 'cd', 'echo',
        # Python
        'python', 'python3', 'pip', 'pip3', 'pytest',
        # Node.js
        'node', 'npm', 'npx', 'yarn',
        # Git
        'git', 'git status', 'git log', 'git diff', 'git show',
        # Build tools
        'make', 'cmake', 'gcc', 'g++', 'clang',
        # Utilities
        'curl', 'wget', 'tar', 'gzip', 'gunzip', 'zip', 'unzip',
        'mkdir', 'rm', 'cp', 'mv', 'touch', 'chmod', 'chown',
        'which', 'where', 'whoami', 'date', 'time',
    }
    
    # Límites de seguridad
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_OUTPUT_SIZE = 1 * 1024 * 1024  # 1MB
    DEFAULT_TIMEOUT = 30
    MAX_TIMEOUT = 300  # 5 minutos
    
    def __init__(self, working_dir: str):
        """
        Inicializar executor con un directorio de trabajo base.
        
        Args:
            working_dir: Directorio base que no se puede escapar
        """
        self.working_dir = Path(working_dir).resolve()
        if not self.working_dir.exists():
            self.working_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ToolExecutor inicializado con working_dir: {self.working_dir}")
    
    def _resolve_path(self, path: str) -> Path:
        """
        Resolver y validar un path.
        
        Asegura que el path resuelto esté dentro del working_dir.
        Soporta paths absolutos y relativos.
        
        Args:
            path: Path a resolver
            
        Returns:
            Path resuelto y validado
            
        Raises:
            ValueError: Si el path escapa del working_dir
        """
        if not path:
            raise ValueError("Path no puede estar vacío")
        
        # Convertir a Path y resolver
        input_path = Path(path)
        
        if input_path.is_absolute():
            resolved = input_path.resolve()
        else:
            resolved = (self.working_dir / input_path).resolve()
        
        # Verificar que no escapa del working_dir
        try:
            resolved.relative_to(self.working_dir)
        except ValueError:
            raise ValueError(
                f"Path '{path}' escapa del directorio de trabajo permitido. "
                f"Solo se permite acceder a archivos dentro de {self.working_dir}"
            )
        
        return resolved
    
    def _validate_file_size(self, path: Path) -> None:
        """Validar que un archivo no exceda el tamaño máximo"""
        if path.exists() and path.is_file():
            size = path.stat().st_size
            if size > self.MAX_FILE_SIZE:
                raise ValueError(
                    f"Archivo '{path}' ({size} bytes) excede el límite de "
                    f"{self.MAX_FILE_SIZE} bytes ({self.MAX_FILE_SIZE // (1024*1024)}MB)"
                )
    
    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """
        Ejecutar una tool por nombre con los argumentos dados.
        
        Args:
            tool_name: Nombre de la tool a ejecutar
            arguments: Argumentos para la tool
            
        Returns:
            ToolResult con el resultado de la ejecución
        """
        logger.info(f"Ejecutando tool: {tool_name} con args: {arguments}")
        
        try:
            if tool_name == "read_file":
                return await self.read_file(**arguments)
            elif tool_name == "write_file":
                return await self.write_file(**arguments)
            elif tool_name == "edit_file":
                return await self.edit_file(**arguments)
            elif tool_name == "list_directory":
                return await self.list_directory(**arguments)
            elif tool_name == "execute_command":
                return await self.execute_command(**arguments)
            else:
                return ToolResult(
                    success=False,
                    content="",
                    error=f"Tool desconocida: {tool_name}"
                )
        except Exception as e:
            logger.error(f"Error ejecutando tool {tool_name}: {e}")
            return ToolResult(
                success=False,
                content="",
                error=f"Error ejecutando {tool_name}: {str(e)}"
            )
    
    async def read_file(self, path: str) -> ToolResult:
        """
        Leer el contenido de un archivo.
        
        Args:
            path: Path al archivo (relativo o absoluto)
            
        Returns:
            ToolResult con el contenido del archivo
        """
        try:
            file_path = self._resolve_path(path)
            
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    content="",
                    error=f"Archivo no encontrado: {path}"
                )
            
            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    content="",
                    error=f"La ruta '{path}' no es un archivo"
                )
            
            self._validate_file_size(file_path)
            
            # Leer archivo
            content = file_path.read_text(encoding='utf-8', errors='replace')
            
            # Truncar si es muy grande
            if len(content) > self.MAX_OUTPUT_SIZE:
                content = content[:self.MAX_OUTPUT_SIZE] + (
                    f"\n... [Contenido truncado, mostrando {self.MAX_OUTPUT_SIZE} "
                    f"de {len(content)} caracteres]"
                )
            
            logger.info(f"Archivo leído exitosamente: {file_path}")
            return ToolResult(success=True, content=content)
            
        except ValueError as e:
            return ToolResult(success=False, content="", error=str(e))
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"Error leyendo archivo: {str(e)}"
            )
    
    async def write_file(self, path: str, content: str) -> ToolResult:
        """
        Escribir contenido a un archivo.
        
        Args:
            path: Path al archivo (relativo o absoluto)
            content: Contenido a escribir
            
        Returns:
            ToolResult confirmando la escritura
        """
        try:
            file_path = self._resolve_path(path)
            
            # Crear directorios padre si no existen
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Verificar tamaño del contenido
            content_bytes = content.encode('utf-8')
            if len(content_bytes) > self.MAX_FILE_SIZE:
                return ToolResult(
                    success=False,
                    content="",
                    error=f"Contenido ({len(content_bytes)} bytes) excede el límite de {self.MAX_FILE_SIZE} bytes"
                )
            
            # Escribir archivo
            file_path.write_text(content, encoding='utf-8')
            
            # Calcular líneas y caracteres
            lines = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
            chars = len(content)
            
            result_msg = f"Archivo escrito exitosamente: {path}\n"
            result_msg += f"Líneas: {lines}, Caracteres: {chars}"
            
            logger.info(f"Archivo escrito: {file_path} ({lines} líneas, {chars} chars)")
            return ToolResult(success=True, content=result_msg)
            
        except ValueError as e:
            return ToolResult(success=False, content="", error=str(e))
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"Error escribiendo archivo: {str(e)}"
            )
    
    async def edit_file(self, path: str, old_string: str, new_string: str) -> ToolResult:
        """
        Editar un archivo reemplazando old_string por new_string.
        
        Args:
            path: Path al archivo
            old_string: String a buscar y reemplazar
            new_string: String nuevo
            
        Returns:
            ToolResult confirmando la edición
        """
        try:
            file_path = self._resolve_path(path)
            
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    content="",
                    error=f"Archivo no encontrado: {path}"
                )
            
            self._validate_file_size(file_path)
            
            # Leer contenido actual
            content = file_path.read_text(encoding='utf-8')
            
            # Verificar que old_string existe
            if old_string not in content:
                return ToolResult(
                    success=False,
                    content="",
                    error=f"No se encontró el string a reemplazar en {path}. "
                           f"Asegúrate de que el string coincida exactamente (incluyendo espacios y saltos de línea)."
                )
            
            # Contar ocurrencias
            occurrences = content.count(old_string)
            if occurrences > 1:
                logger.warning(f"String encontrado {occurrences} veces, reemplazando primera ocurrencia")
            
            # Reemplazar (solo primera ocurrencia)
            new_content = content.replace(old_string, new_string, 1)
            
            # Escribir nuevo contenido
            file_path.write_text(new_content, encoding='utf-8')
            
            result_msg = f"Archivo editado exitosamente: {path}\n"
            result_msg += f"Reemplazadas: {min(occurrences, 1)} ocurrencia(s) de {occurrences} encontrada(s)"
            
            logger.info(f"Archivo editado: {file_path}")
            return ToolResult(success=True, content=result_msg)
            
        except ValueError as e:
            return ToolResult(success=False, content="", error=str(e))
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"Error editando archivo: {str(e)}"
            )
    
    async def list_directory(self, path: str = ".") -> ToolResult:
        """
        Listar contenido de un directorio.
        
        Args:
            path: Path al directorio (default: directorio actual)
            
        Returns:
            ToolResult con lista de archivos y directorios
        """
        try:
            dir_path = self._resolve_path(path)
            
            if not dir_path.exists():
                return ToolResult(
                    success=False,
                    content="",
                    error=f"Directorio no encontrado: {path}"
                )
            
            if not dir_path.is_dir():
                return ToolResult(
                    success=False,
                    content="",
                    error=f"La ruta '{path}' no es un directorio"
                )
            
            # Listar contenido
            items = []
            for item in sorted(dir_path.iterdir()):
                item_type = "📁" if item.is_dir() else "📄"
                size = ""
                if item.is_file():
                    size_bytes = item.stat().st_size
                    if size_bytes < 1024:
                        size = f" ({size_bytes}B)"
                    elif size_bytes < 1024 * 1024:
                        size = f" ({size_bytes / 1024:.1f}KB)"
                    else:
                        size = f" ({size_bytes / (1024 * 1024):.1f}MB)"
                
                items.append(f"{item_type} {item.name}{size}")
            
            if not items:
                result = f"Directorio vacío: {path}"
            else:
                result = f"Contenido de '{path}':\n" + "\n".join(items)
            
            logger.info(f"Directorio listado: {dir_path} ({len(items)} items)")
            return ToolResult(success=True, content=result)
            
        except ValueError as e:
            return ToolResult(success=False, content="", error=str(e))
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"Error listando directorio: {str(e)}"
            )
    
    async def execute_command(self, command: str, timeout: int = DEFAULT_TIMEOUT) -> ToolResult:
        """
        Ejecutar un comando shell.
        
        Args:
            command: Comando a ejecutar
            timeout: Timeout en segundos (default: 30, max: 300)
            
        Returns:
            ToolResult con stdout/stderr
        """
        try:
            # Validar timeout
            timeout = min(max(timeout, 1), self.MAX_TIMEOUT)
            
            # Validar comando contra whitelist
            cmd_parts = command.strip().split()
            if not cmd_parts:
                return ToolResult(
                    success=False,
                    content="",
                    error="Comando vacío"
                )
            
            base_cmd = cmd_parts[0].lower()
            
            # Verificar si el comando base está en whitelist
            # O si el comando completo está en whitelist
            is_allowed = False
            if base_cmd in self.ALLOWED_COMMANDS:
                is_allowed = True
            elif command.strip().lower() in self.ALLOWED_COMMANDS:
                is_allowed = True
            
            if not is_allowed:
                allowed_list = ", ".join(sorted(self.ALLOWED_COMMANDS))[:200]
                return ToolResult(
                    success=False,
                    content="",
                    error=f"Comando '{base_cmd}' no está permitido. "
                           f"Comandos permitidos incluyen: {allowed_list}..."
                )
            
            logger.info(f"Ejecutando comando: {command} (timeout: {timeout}s)")
            
            # Ejecutar comando
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            # Construir output
            output_parts = []
            if result.stdout:
                output_parts.append("STDOUT:")
                output_parts.append(result.stdout)
            if result.stderr:
                output_parts.append("\nSTDERR:")
                output_parts.append(result.stderr)
            
            output = "\n".join(output_parts) if output_parts else "(sin salida)"
            
            # Truncar si es muy largo
            if len(output) > self.MAX_OUTPUT_SIZE:
                output = output[:self.MAX_OUTPUT_SIZE] + (
                    f"\n... [Salida truncada, mostrando {self.MAX_OUTPUT_SIZE} "
                    f"de {len(output)} caracteres]"
                )
            
            success = result.returncode == 0
            logger.info(f"Comando completado con código: {result.returncode}")
            
            return ToolResult(
                success=success,
                content=output,
                error=None if success else f"Exit code: {result.returncode}"
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                content="",
                error=f"Comando expiró después de {timeout} segundos"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"Error ejecutando comando: {str(e)}"
            )
