"""
Skill loader and plugin manager for dynamic skill loading.

This module provides functionality for:
    - Loading skills from Python modules
    - Loading skills from packages
    - Hot-reloading for development
    - Plugin lifecycle management
    - Dependency resolution
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, Callable
from dataclasses import dataclass, field
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from docmcp.skills.base import BaseSkill, SkillMetadata
from docmcp.skills.registry import SkillRegistry, skill_registry

logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    """Information about a loaded plugin."""
    
    name: str
    path: Path
    module: Any = None
    skills: List[Type[BaseSkill]] = field(default_factory=list)
    loaded_at: float = field(default_factory=lambda: __import__('time').time())
    last_modified: float = field(default_factory=lambda: __import__('time').time())
    dependencies: List[str] = field(default_factory=list)
    
    @property
    def skill_count(self) -> int:
        """Number of skills in this plugin."""
        return len(self.skills)


class SkillLoader:
    """
    Dynamic skill loader.
    
    Loads skills from Python modules and packages at runtime.
    
    Example:
        >>> loader = SkillLoader(skill_registry)
        >>> 
        >>> # Load from file
        >>> loader.load_from_file("/path/to/my_skill.py")
        >>> 
        >>> # Load from directory
        >>> loader.load_from_directory("/path/to/skills/")
        >>> 
        >>> # Load from module
        >>> loader.load_from_module("my_package.skills")
    """
    
    def __init__(self, registry: Optional[SkillRegistry] = None):
        self.registry = registry or skill_registry
        self._loaded_plugins: Dict[str, PluginInfo] = {}
        self._module_cache: Dict[str, Any] = {}
    
    def load_from_file(
        self,
        file_path: Union[str, Path],
        register: bool = True,
    ) -> Optional[PluginInfo]:
        """
        Load skills from a Python file.
        
        Args:
            file_path: Path to Python file
            register: Whether to register loaded skills
            
        Returns:
            PluginInfo if loaded successfully
        """
        path = Path(file_path)
        
        if not path.exists():
            logger.error(f"File not found: {path}")
            return None
        
        if not path.suffix == ".py":
            logger.error(f"Not a Python file: {path}")
            return None
        
        try:
            # Create module spec
            module_name = f"_skill_{path.stem}_{hash(str(path)) % 10000}"
            spec = importlib.util.spec_from_file_location(module_name, path)
            
            if spec is None or spec.loader is None:
                logger.error(f"Could not create module spec for: {path}")
                return None
            
            # Load module
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Find skill classes
            skills = self._extract_skills(module)
            
            # Register skills
            if register:
                for skill_class in skills:
                    self.registry.register(skill_class)
            
            # Store plugin info
            plugin_info = PluginInfo(
                name=path.stem,
                path=path,
                module=module,
                skills=skills,
            )
            self._loaded_plugins[plugin_info.name] = plugin_info
            
            logger.info(f"Loaded {len(skills)} skills from {path}")
            return plugin_info
            
        except Exception as e:
            logger.exception(f"Failed to load skills from {path}: {e}")
            return None
    
    def load_from_directory(
        self,
        directory: Union[str, Path],
        pattern: str = "*.py",
        recursive: bool = True,
        register: bool = True,
    ) -> List[PluginInfo]:
        """
        Load skills from a directory.
        
        Args:
            directory: Directory path
            pattern: File pattern to match
            recursive: Whether to search recursively
            register: Whether to register loaded skills
            
        Returns:
            List of loaded PluginInfo
        """
        dir_path = Path(directory)
        
        if not dir_path.exists():
            logger.error(f"Directory not found: {dir_path}")
            return []
        
        loaded = []
        
        if recursive:
            files = dir_path.rglob(pattern)
        else:
            files = dir_path.glob(pattern)
        
        for file_path in files:
            # Skip __init__.py and test files
            if file_path.name.startswith("__") or file_path.name.startswith("test_"):
                continue
            
            plugin_info = self.load_from_file(file_path, register)
            if plugin_info:
                loaded.append(plugin_info)
        
        logger.info(f"Loaded {len(loaded)} plugins from {dir_path}")
        return loaded
    
    def load_from_module(
        self,
        module_name: str,
        register: bool = True,
    ) -> Optional[PluginInfo]:
        """
        Load skills from an installed module.
        
        Args:
            module_name: Module name
            register: Whether to register loaded skills
            
        Returns:
            PluginInfo if loaded successfully
        """
        try:
            # Import module
            if module_name in self._module_cache:
                module = self._module_cache[module_name]
            else:
                module = importlib.import_module(module_name)
                self._module_cache[module_name] = module
            
            # Find skill classes
            skills = self._extract_skills(module)
            
            # Register skills
            if register:
                for skill_class in skills:
                    self.registry.register(skill_class)
            
            # Store plugin info
            plugin_info = PluginInfo(
                name=module_name,
                path=Path(getattr(module, "__file__", "")),
                module=module,
                skills=skills,
            )
            self._loaded_plugins[module_name] = plugin_info
            
            logger.info(f"Loaded {len(skills)} skills from module {module_name}")
            return plugin_info
            
        except Exception as e:
            logger.exception(f"Failed to load module {module_name}: {e}")
            return None
    
    def _extract_skills(self, module: Any) -> List[Type[BaseSkill]]:
        """
        Extract skill classes from a module.
        
        Args:
            module: Python module
            
        Returns:
            List of skill classes
        """
        skills = []
        
        for name in dir(module):
            obj = getattr(module, name)
            
            # Check if it's a skill class
            if (
                isinstance(obj, type) and
                issubclass(obj, BaseSkill) and
                obj is not BaseSkill and
                getattr(obj, "name", None)  # Must have a name
            ):
                skills.append(obj)
        
        return skills
    
    def reload_plugin(self, name: str) -> Optional[PluginInfo]:
        """
        Reload a loaded plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            New PluginInfo if reloaded successfully
        """
        plugin_info = self._loaded_plugins.get(name)
        if plugin_info is None:
            logger.error(f"Plugin not found: {name}")
            return None
        
        # Unregister old skills
        for skill_class in plugin_info.skills:
            self.registry.unregister(skill_class.name)
        
        # Reload
        if plugin_info.path and plugin_info.path.exists():
            return self.load_from_file(plugin_info.path)
        elif plugin_info.module:
            module_name = plugin_info.module.__name__
            # Remove from cache to force reload
            if module_name in self._module_cache:
                del self._module_cache[module_name]
            if module_name in sys.modules:
                del sys.modules[module_name]
            return self.load_from_module(module_name)
        
        return None
    
    def unload_plugin(self, name: str) -> bool:
        """
        Unload a plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            True if unloaded successfully
        """
        plugin_info = self._loaded_plugins.get(name)
        if plugin_info is None:
            return False
        
        # Unregister skills
        for skill_class in plugin_info.skills:
            self.registry.unregister(skill_class.name)
        
        # Remove from loaded plugins
        del self._loaded_plugins[name]
        
        logger.info(f"Unloaded plugin: {name}")
        return True
    
    def get_loaded_plugins(self) -> Dict[str, PluginInfo]:
        """Get all loaded plugins."""
        return dict(self._loaded_plugins)
    
    def get_plugin_info(self, name: str) -> Optional[PluginInfo]:
        """Get information about a loaded plugin."""
        return self._loaded_plugins.get(name)


class PluginManager:
    """
    Plugin manager with hot-reload support.
    
    Manages plugin lifecycle and provides hot-reloading for development.
    
    Example:
        >>> manager = PluginManager(skill_registry)
        >>> 
        >>> # Add plugin directory
        >>> manager.add_directory("/path/to/plugins/")
        >>> 
        >>> # Start watching for changes
        >>> await manager.start_watching()
        >>> 
        >>> # Stop watching
        >>> await manager.stop_watching()
    """
    
    def __init__(
        self,
        registry: Optional[SkillRegistry] = None,
        auto_reload: bool = True,
    ):
        self.registry = registry or skill_registry
        self.loader = SkillLoader(registry)
        self.auto_reload = auto_reload
        
        self._watched_directories: Set[Path] = set()
        self._observer: Optional[Observer] = None
        self._event_handler: Optional[FileSystemEventHandler] = None
        self._running = False
    
    def add_directory(self, directory: Union[str, Path]) -> None:
        """
        Add a directory to watch for plugins.
        
        Args:
            directory: Directory path
        """
        dir_path = Path(directory)
        self._watched_directories.add(dir_path)
        
        # Load existing plugins
        self.loader.load_from_directory(dir_path)
    
    def remove_directory(self, directory: Union[str, Path]) -> None:
        """
        Remove a directory from watch list.
        
        Args:
            directory: Directory path
        """
        dir_path = Path(directory)
        self._watched_directories.discard(dir_path)
    
    async def start_watching(self) -> None:
        """Start watching for file changes."""
        if self._running or not self.auto_reload:
            return
        
        self._running = True
        
        # Create event handler
        self._event_handler = PluginEventHandler(self.loader)
        
        # Create observer
        self._observer = Observer()
        
        for directory in self._watched_directories:
            self._observer.schedule(
                self._event_handler,
                str(directory),
                recursive=True,
            )
        
        self._observer.start()
        logger.info("Started watching for plugin changes")
    
    async def stop_watching(self) -> None:
        """Stop watching for file changes."""
        if not self._running:
            return
        
        self._running = False
        
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        
        logger.info("Stopped watching for plugin changes")
    
    def load_plugin(self, path: Union[str, Path]) -> Optional[PluginInfo]:
        """
        Load a plugin from path.
        
        Args:
            path: Path to plugin file or directory
            
        Returns:
            PluginInfo if loaded successfully
        """
        path_obj = Path(path)
        
        if path_obj.is_file():
            return self.loader.load_from_file(path_obj)
        elif path_obj.is_dir():
            plugins = self.loader.load_from_directory(path_obj)
            return plugins[0] if plugins else None
        
        return None
    
    def unload_plugin(self, name: str) -> bool:
        """
        Unload a plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            True if unloaded successfully
        """
        return self.loader.unload_plugin(name)
    
    def reload_plugin(self, name: str) -> Optional[PluginInfo]:
        """
        Reload a plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            New PluginInfo if reloaded successfully
        """
        return self.loader.reload_plugin(name)
    
    def get_loaded_plugins(self) -> Dict[str, PluginInfo]:
        """Get all loaded plugins."""
        return self.loader.get_loaded_plugins()


class PluginEventHandler(FileSystemEventHandler):
    """File system event handler for plugin hot-reload."""
    
    def __init__(self, loader: SkillLoader):
        self.loader = loader
    
    def on_modified(self, event):
        """Handle file modification event."""
        if event.is_directory:
            return
        
        if not event.src_path.endswith(".py"):
            return
        
        file_path = Path(event.src_path)
        
        # Skip certain files
        if file_path.name.startswith("__") or file_path.name.startswith("test_"):
            return
        
        logger.info(f"Plugin file modified: {file_path}")
        
        # Find and reload plugin
        for name, info in self.loader.get_loaded_plugins().items():
            if info.path == file_path:
                logger.info(f"Reloading plugin: {name}")
                self.loader.reload_plugin(name)
                break
        else:
            # New file, try to load it
            self.loader.load_from_file(file_path)


# Type hints
from typing import Union
