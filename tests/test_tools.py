"""
Tests para el sistema de Tools
"""
import pytest
import os
import tempfile
from pathlib import Path


@pytest.mark.asyncio
async def test_tool_executor_initialization():
    """Test que ToolExecutor se inicializa correctamente"""
    from core.tools.executor import ToolExecutor
    
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = ToolExecutor(tmpdir)
        assert executor.working_dir == Path(tmpdir).resolve()


@pytest.mark.asyncio
async def test_read_file_tool():
    """Test la tool read_file"""
    from core.tools.executor import ToolExecutor
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Crear archivo de prueba
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Hello, World!")
        
        executor = ToolExecutor(tmpdir)
        result = await executor.read_file("test.txt")
        
        assert result.success is True
        assert result.content == "Hello, World!"
        assert result.error is None


@pytest.mark.asyncio
async def test_read_file_not_found():
    """Test read_file con archivo inexistente"""
    from core.tools.executor import ToolExecutor
    
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = ToolExecutor(tmpdir)
        result = await executor.read_file("nonexistent.txt")
        
        assert result.success is False
        assert "no encontrado" in result.error.lower() or "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_read_file_path_traversal():
    """Test que read_file bloquea path traversal"""
    from core.tools.executor import ToolExecutor
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Crear archivo fuera del working_dir
        outside_file = Path(tmpdir).parent / "secret.txt"
        outside_file.write_text("secret")
        
        executor = ToolExecutor(tmpdir)
        
        # Intentar leer archivo fuera del working_dir
        result = await executor.read_file("../secret.txt")
        
        assert result.success is False
        # Debe fallar por seguridad


@pytest.mark.asyncio
async def test_write_file_tool():
    """Test la tool write_file"""
    from core.tools.executor import ToolExecutor
    
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = ToolExecutor(tmpdir)
        result = await executor.write_file("newfile.txt", "New content")
        
        assert result.success is True
        
        # Verificar que se creó
        created_file = Path(tmpdir) / "newfile.txt"
        assert created_file.exists()
        assert created_file.read_text() == "New content"


@pytest.mark.asyncio
async def test_write_file_creates_directories():
    """Test que write_file crea directorios padre"""
    from core.tools.executor import ToolExecutor
    
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = ToolExecutor(tmpdir)
        result = await executor.write_file("subdir/nested/file.txt", "Content")
        
        assert result.success is True
        
        created_file = Path(tmpdir) / "subdir" / "nested" / "file.txt"
        assert created_file.exists()


@pytest.mark.asyncio
async def test_edit_file_tool():
    """Test la tool edit_file"""
    from core.tools.executor import ToolExecutor
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Crear archivo
        test_file = Path(tmpdir) / "editable.txt"
        test_file.write_text("Hello, Old World!")
        
        executor = ToolExecutor(tmpdir)
        result = await executor.edit_file(
            "editable.txt",
            old_string="Old",
            new_string="New"
        )
        
        assert result.success is True
        assert test_file.read_text() == "Hello, New World!"


@pytest.mark.asyncio
async def test_edit_file_string_not_found():
    """Test edit_file cuando el string no existe"""
    from core.tools.executor import ToolExecutor
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Original content")
        
        executor = ToolExecutor(tmpdir)
        result = await executor.edit_file(
            "test.txt",
            old_string="NonExistent",
            new_string="Replacement"
        )
        
        assert result.success is False


@pytest.mark.asyncio
async def test_list_directory_tool():
    """Test la tool list_directory"""
    from core.tools.executor import ToolExecutor
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Crear archivos y directorios
        (Path(tmpdir) / "file1.txt").write_text("content")
        (Path(tmpdir) / "file2.txt").write_text("content")
        (Path(tmpdir) / "subdir").mkdir()
        
        executor = ToolExecutor(tmpdir)
        result = await executor.list_directory(".")
        
        assert result.success is True
        assert "file1.txt" in result.content
        assert "file2.txt" in result.content
        assert "subdir" in result.content


@pytest.mark.asyncio
async def test_execute_command_allowed():
    """Test execute_command con comando permitido"""
    from core.tools.executor import ToolExecutor
    
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = ToolExecutor(tmpdir)
        
        # Crear archivo para listar
        (Path(tmpdir) / "test.txt").write_text("content")
        
        # Ejecutar ls/dir según el sistema
        import sys
        if sys.platform == "win32":
            result = await executor.execute_command("dir")
        else:
            result = await executor.execute_command("ls -la")
        
        # Nota: Puede fallar por el comando específico, pero no debe ser por seguridad
        # Solo verificamos que no falle por "comando no permitido"
        if not result.success:
            assert "no está permitido" not in result.error.lower()
            assert "not allowed" not in result.error.lower()


@pytest.mark.asyncio
async def test_execute_command_not_allowed():
    """Test execute_command rechaza comandos no permitidos"""
    from core.tools.executor import ToolExecutor
    
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = ToolExecutor(tmpdir)
        # Usar un comando que NO está en el whitelist
        result = await executor.execute_command("sudo rm -rf /")
        
        assert result.success is False
        assert "no está permitido" in result.error.lower() or "not allowed" in result.error.lower()


@pytest.mark.asyncio
async def test_tool_executor_with_api():
    """Test integración básica de tools con API"""
    # Este test verifica que las tools están disponibles en el endpoint
    # No ejecuta tools reales, solo verifica la estructura
    from core.tools import TOOLS, TOOL_DEFINITIONS
    
    assert "read_file" in TOOLS
    assert "write_file" in TOOLS
    assert "edit_file" in TOOLS
    assert "list_directory" in TOOLS
    assert "execute_command" in TOOLS
    
    assert len(TOOL_DEFINITIONS) == 5


@pytest.mark.asyncio
async def test_tool_definitions_format():
    """Test que las tool definitions tienen el formato correcto"""
    from core.tools import TOOL_DEFINITIONS
    
    for tool in TOOL_DEFINITIONS:
        assert "type" in tool
        assert "function" in tool
        assert "name" in tool["function"]
        assert "description" in tool["function"]
        assert "parameters" in tool["function"]
