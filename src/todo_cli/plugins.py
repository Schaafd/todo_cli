"""Plugin Architecture for Todo CLI.

This module provides an extensible plugin system that allows custom analytics,
integrations, and workflow extensions with proper API and documentation.

Features:
- Plugin discovery and loading
- Lifecycle management
- Event system for plugin communication
- API interfaces for analytics and dashboard extensions
- Security and sandboxing
- Plugin marketplace support
"""

import os
import sys
import json
import uuid
import importlib
import importlib.util
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional, Type, Callable, Union
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import inspect

from .todo import Todo, Priority, TodoStatus
from .analytics import AnalyticsReport, ProductivityAnalyzer
from .dashboard import Widget, WidgetData, DataSource, Dashboard
from .config import get_config


class PluginType(Enum):
    """Types of plugins"""
    ANALYTICS = "analytics"         # Analytics and insights plugins
    DASHBOARD = "dashboard"         # Dashboard widgets and data sources
    INTEGRATION = "integration"     # Third-party integrations
    WORKFLOW = "workflow"          # Workflow automation
    EXPORT = "export"              # Export formatters
    NOTIFICATION = "notification"   # Notification providers
    THEME = "theme"                # UI themes
    UTILITY = "utility"            # Utility functions


class PluginStatus(Enum):
    """Plugin status states"""
    DISABLED = "disabled"
    ENABLED = "enabled"
    ERROR = "error"
    LOADING = "loading"
    UNLOADED = "unloaded"


@dataclass
class PluginInfo:
    """Plugin metadata and information"""
    id: str
    name: str
    version: str
    author: str
    description: str
    plugin_type: PluginType
    
    # Dependencies and requirements
    min_cli_version: str = "1.0.0"
    dependencies: List[str] = field(default_factory=list)
    python_requires: str = ">=3.8"
    
    # Plugin files and entry points
    entry_point: str = "main.py"
    config_schema: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    homepage: Optional[str] = None
    license: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    
    # Runtime status
    status: PluginStatus = PluginStatus.DISABLED
    error_message: Optional[str] = None
    loaded_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'version': self.version,
            'author': self.author,
            'description': self.description,
            'plugin_type': self.plugin_type.value,
            'min_cli_version': self.min_cli_version,
            'dependencies': self.dependencies,
            'python_requires': self.python_requires,
            'entry_point': self.entry_point,
            'config_schema': self.config_schema,
            'homepage': self.homepage,
            'license': self.license,
            'keywords': self.keywords,
            'status': self.status.value,
            'error_message': self.error_message,
            'loaded_at': self.loaded_at.isoformat() if self.loaded_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginInfo':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            name=data['name'],
            version=data['version'],
            author=data['author'],
            description=data['description'],
            plugin_type=PluginType(data['plugin_type']),
            min_cli_version=data.get('min_cli_version', '1.0.0'),
            dependencies=data.get('dependencies', []),
            python_requires=data.get('python_requires', '>=3.8'),
            entry_point=data.get('entry_point', 'main.py'),
            config_schema=data.get('config_schema', {}),
            homepage=data.get('homepage'),
            license=data.get('license'),
            keywords=data.get('keywords', []),
            status=PluginStatus(data.get('status', 'disabled')),
            error_message=data.get('error_message'),
            loaded_at=datetime.fromisoformat(data['loaded_at']) if data.get('loaded_at') else None
        )


class PluginAPI:
    """API interface exposed to plugins"""
    
    def __init__(self, plugin_manager: 'PluginManager'):
        self.plugin_manager = plugin_manager
        self.config = get_config()
    
    def get_todos(self) -> List[Todo]:
        """Get all todos - plugins can use this for analysis"""
        # In a real implementation, this would connect to the todo storage
        return []
    
    def get_analytics_report(self, timeframe: str = "weekly") -> AnalyticsReport:
        """Get analytics report"""
        analyzer = ProductivityAnalyzer()
        from .analytics import AnalyticsTimeframe
        return analyzer.analyze_productivity(self.get_todos(), AnalyticsTimeframe(timeframe))
    
    def register_dashboard_widget(self, widget_class: Type[DataSource]):
        """Register a custom dashboard widget data source"""
        if hasattr(self.plugin_manager, 'dashboard_manager'):
            widget_instance = widget_class()
            self.plugin_manager.dashboard_manager.data_sources[widget_instance.name] = widget_instance
    
    def emit_event(self, event_type: str, data: Any):
        """Emit an event to other plugins"""
        self.plugin_manager.emit_event(event_type, data)
    
    def subscribe_to_event(self, event_type: str, handler: Callable):
        """Subscribe to events from other plugins"""
        self.plugin_manager.subscribe_to_event(event_type, handler)
    
    def log(self, level: str, message: str):
        """Log a message through the plugin system"""
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] PLUGIN {level.upper()}: {message}")
    
    def get_plugin_config(self, plugin_id: str) -> Dict[str, Any]:
        """Get configuration for a plugin"""
        return self.plugin_manager.get_plugin_config(plugin_id)
    
    def set_plugin_config(self, plugin_id: str, config: Dict[str, Any]):
        """Set configuration for a plugin"""
        self.plugin_manager.set_plugin_config(plugin_id, config)


class BasePlugin(ABC):
    """Base class for all plugins"""
    
    def __init__(self, api: PluginAPI):
        self.api = api
        self.info: Optional[PluginInfo] = None
        self.config: Dict[str, Any] = {}
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the plugin. Return True if successful."""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Clean up resources when plugin is unloaded"""
        pass
    
    def get_info(self) -> PluginInfo:
        """Get plugin information"""
        if self.info:
            return self.info
        
        # Default info - should be overridden
        return PluginInfo(
            id="unknown",
            name="Unknown Plugin",
            version="1.0.0",
            author="Unknown",
            description="No description provided",
            plugin_type=PluginType.UTILITY
        )
    
    def on_event(self, event_type: str, data: Any):
        """Handle events from other plugins"""
        pass


class AnalyticsPlugin(BasePlugin):
    """Base class for analytics plugins"""
    
    @abstractmethod
    def analyze(self, todos: List[Todo]) -> Dict[str, Any]:
        """Analyze todos and return insights"""
        pass
    
    @abstractmethod
    def get_metrics(self, todos: List[Todo]) -> Dict[str, float]:
        """Get quantitative metrics from todos"""
        pass


class DashboardPlugin(BasePlugin):
    """Base class for dashboard plugins"""
    
    @abstractmethod
    def get_widget_types(self) -> List[str]:
        """Get list of widget types provided by this plugin"""
        pass
    
    @abstractmethod
    def create_data_source(self, widget_type: str) -> DataSource:
        """Create a data source for the specified widget type"""
        pass


class IntegrationPlugin(BasePlugin):
    """Base class for integration plugins"""
    
    @abstractmethod
    def sync_data(self, direction: str = "bidirectional") -> bool:
        """Sync data with external service"""
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """Test connection to external service"""
        pass


class WorkflowPlugin(BasePlugin):
    """Base class for workflow plugins"""
    
    @abstractmethod
    def execute_workflow(self, trigger: str, data: Any) -> bool:
        """Execute workflow based on trigger"""
        pass
    
    @abstractmethod
    def get_triggers(self) -> List[str]:
        """Get list of supported triggers"""
        pass


class PluginManager:
    """Main plugin management system"""
    
    def __init__(self):
        self.config = get_config()
        self.plugins_dir = Path(self.config.data_dir) / "plugins"
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        
        self.installed_plugins: Dict[str, PluginInfo] = {}
        self.loaded_plugins: Dict[str, BasePlugin] = {}
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}
        
        # Initialize API
        self.api = PluginAPI(self)
        
        # Load plugin registry
        self._load_plugin_registry()
        self._load_plugin_configs()
    
    def _load_plugin_registry(self):
        """Load plugin registry from disk"""
        registry_file = self.plugins_dir / "registry.json"
        if registry_file.exists():
            try:
                with open(registry_file, 'r') as f:
                    data = json.load(f)
                
                for plugin_data in data.get('plugins', []):
                    plugin_info = PluginInfo.from_dict(plugin_data)
                    self.installed_plugins[plugin_info.id] = plugin_info
            except Exception as e:
                print(f"Error loading plugin registry: {e}")
    
    def _save_plugin_registry(self):
        """Save plugin registry to disk"""
        registry_file = self.plugins_dir / "registry.json"
        try:
            data = {
                'plugins': [plugin.to_dict() for plugin in self.installed_plugins.values()],
                'updated': datetime.now().isoformat()
            }
            
            with open(registry_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving plugin registry: {e}")
    
    def _load_plugin_configs(self):
        """Load plugin configurations"""
        configs_file = self.plugins_dir / "configs.json"
        if configs_file.exists():
            try:
                with open(configs_file, 'r') as f:
                    self.plugin_configs = json.load(f)
            except Exception as e:
                print(f"Error loading plugin configs: {e}")
    
    def _save_plugin_configs(self):
        """Save plugin configurations"""
        configs_file = self.plugins_dir / "configs.json"
        try:
            with open(configs_file, 'w') as f:
                json.dump(self.plugin_configs, f, indent=2)
        except Exception as e:
            print(f"Error saving plugin configs: {e}")
    
    def discover_plugins(self) -> List[str]:
        """Discover available plugins in the plugins directory"""
        discovered = []
        
        for plugin_dir in self.plugins_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith('.'):
                manifest_file = plugin_dir / "plugin.json"
                if manifest_file.exists():
                    discovered.append(plugin_dir.name)
        
        return discovered
    
    def install_plugin(self, plugin_path: str) -> bool:
        """Install a plugin from a directory or archive"""
        plugin_path_obj = Path(plugin_path)
        
        if not plugin_path_obj.exists():
            print(f"Plugin path does not exist: {plugin_path}")
            return False
        
        # Read plugin manifest
        if plugin_path_obj.is_dir():
            manifest_file = plugin_path_obj / "plugin.json"
        else:
            # Handle archive files in the future
            print("Archive installation not yet implemented")
            return False
        
        if not manifest_file.exists():
            print("No plugin.json manifest found")
            return False
        
        try:
            with open(manifest_file, 'r') as f:
                manifest = json.load(f)
            
            plugin_info = PluginInfo(
                id=manifest['id'],
                name=manifest['name'],
                version=manifest['version'],
                author=manifest['author'],
                description=manifest['description'],
                plugin_type=PluginType(manifest['type']),
                min_cli_version=manifest.get('min_cli_version', '1.0.0'),
                dependencies=manifest.get('dependencies', []),
                python_requires=manifest.get('python_requires', '>=3.8'),
                entry_point=manifest.get('entry_point', 'main.py'),
                config_schema=manifest.get('config_schema', {}),
                homepage=manifest.get('homepage'),
                license=manifest.get('license'),
                keywords=manifest.get('keywords', [])
            )
            
            # Copy plugin files to plugins directory
            plugin_install_dir = self.plugins_dir / plugin_info.id
            if plugin_install_dir.exists():
                print(f"Plugin {plugin_info.id} already installed")
                return False
            
            # Simple file copy (in production, would use proper installation)
            import shutil
            shutil.copytree(plugin_path_obj, plugin_install_dir)
            
            # Register plugin
            self.installed_plugins[plugin_info.id] = plugin_info
            self._save_plugin_registry()
            
            print(f"Plugin {plugin_info.name} installed successfully")
            return True
            
        except Exception as e:
            print(f"Error installing plugin: {e}")
            return False
    
    def uninstall_plugin(self, plugin_id: str) -> bool:
        """Uninstall a plugin"""
        if plugin_id not in self.installed_plugins:
            print(f"Plugin {plugin_id} not found")
            return False
        
        # Unload if loaded
        if plugin_id in self.loaded_plugins:
            self.unload_plugin(plugin_id)
        
        # Remove plugin directory
        plugin_dir = self.plugins_dir / plugin_id
        if plugin_dir.exists():
            import shutil
            shutil.rmtree(plugin_dir)
        
        # Remove from registry
        del self.installed_plugins[plugin_id]
        if plugin_id in self.plugin_configs:
            del self.plugin_configs[plugin_id]
        
        self._save_plugin_registry()
        self._save_plugin_configs()
        
        print(f"Plugin {plugin_id} uninstalled")
        return True
    
    def load_plugin(self, plugin_id: str) -> bool:
        """Load and initialize a plugin"""
        if plugin_id not in self.installed_plugins:
            print(f"Plugin {plugin_id} not installed")
            return False
        
        if plugin_id in self.loaded_plugins:
            print(f"Plugin {plugin_id} already loaded")
            return True
        
        plugin_info = self.installed_plugins[plugin_id]
        plugin_info.status = PluginStatus.LOADING
        
        try:
            # Load plugin module
            plugin_dir = self.plugins_dir / plugin_id
            entry_file = plugin_dir / plugin_info.entry_point
            
            if not entry_file.exists():
                raise Exception(f"Entry point {plugin_info.entry_point} not found")
            
            # Import plugin module
            spec = importlib.util.spec_from_file_location(f"plugin_{plugin_id}", entry_file)
            if spec is None or spec.loader is None:
                raise Exception("Could not load plugin module")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find plugin class
            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, BasePlugin) and 
                    obj is not BasePlugin):
                    plugin_class = obj
                    break
            
            if not plugin_class:
                raise Exception("No plugin class found")
            
            # Create plugin instance
            plugin_instance = plugin_class(self.api)
            plugin_instance.info = plugin_info
            plugin_instance.config = self.plugin_configs.get(plugin_id, {})
            
            # Initialize plugin
            if not plugin_instance.initialize():
                raise Exception("Plugin initialization failed")
            
            # Store loaded plugin
            self.loaded_plugins[plugin_id] = plugin_instance
            plugin_info.status = PluginStatus.ENABLED
            plugin_info.loaded_at = datetime.now()
            plugin_info.error_message = None
            
            print(f"Plugin {plugin_info.name} loaded successfully")
            self.emit_event("plugin_loaded", {'plugin_id': plugin_id})
            
            return True
            
        except Exception as e:
            plugin_info.status = PluginStatus.ERROR
            plugin_info.error_message = str(e)
            print(f"Error loading plugin {plugin_id}: {e}")
            return False
        
        finally:
            self._save_plugin_registry()
    
    def unload_plugin(self, plugin_id: str) -> bool:
        """Unload a plugin"""
        if plugin_id not in self.loaded_plugins:
            print(f"Plugin {plugin_id} not loaded")
            return True
        
        try:
            plugin = self.loaded_plugins[plugin_id]
            plugin.cleanup()
            
            del self.loaded_plugins[plugin_id]
            
            if plugin_id in self.installed_plugins:
                self.installed_plugins[plugin_id].status = PluginStatus.DISABLED
                self.installed_plugins[plugin_id].loaded_at = None
            
            print(f"Plugin {plugin_id} unloaded")
            self.emit_event("plugin_unloaded", {'plugin_id': plugin_id})
            
            return True
            
        except Exception as e:
            print(f"Error unloading plugin {plugin_id}: {e}")
            return False
        
        finally:
            self._save_plugin_registry()
    
    def enable_plugin(self, plugin_id: str) -> bool:
        """Enable and load a plugin"""
        return self.load_plugin(plugin_id)
    
    def disable_plugin(self, plugin_id: str) -> bool:
        """Disable and unload a plugin"""
        return self.unload_plugin(plugin_id)
    
    def list_plugins(self) -> List[PluginInfo]:
        """List all installed plugins"""
        return list(self.installed_plugins.values())
    
    def get_plugin_info(self, plugin_id: str) -> Optional[PluginInfo]:
        """Get information about a specific plugin"""
        return self.installed_plugins.get(plugin_id)
    
    def get_plugin_config(self, plugin_id: str) -> Dict[str, Any]:
        """Get configuration for a plugin"""
        return self.plugin_configs.get(plugin_id, {})
    
    def set_plugin_config(self, plugin_id: str, config: Dict[str, Any]):
        """Set configuration for a plugin"""
        self.plugin_configs[plugin_id] = config
        
        # Update loaded plugin config
        if plugin_id in self.loaded_plugins:
            self.loaded_plugins[plugin_id].config = config
        
        self._save_plugin_configs()
    
    def emit_event(self, event_type: str, data: Any):
        """Emit an event to subscribed handlers"""
        handlers = self.event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                print(f"Error in event handler for {event_type}: {e}")
        
        # Also notify loaded plugins
        for plugin in self.loaded_plugins.values():
            try:
                plugin.on_event(event_type, data)
            except Exception as e:
                print(f"Error in plugin event handler: {e}")
    
    def subscribe_to_event(self, event_type: str, handler: Callable):
        """Subscribe to events"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[PluginInfo]:
        """Get plugins of a specific type"""
        return [plugin for plugin in self.installed_plugins.values() 
                if plugin.plugin_type == plugin_type]
    
    def execute_plugin_method(self, plugin_id: str, method_name: str, *args, **kwargs) -> Any:
        """Execute a method on a loaded plugin"""
        if plugin_id not in self.loaded_plugins:
            raise Exception(f"Plugin {plugin_id} not loaded")
        
        plugin = self.loaded_plugins[plugin_id]
        if not hasattr(plugin, method_name):
            raise Exception(f"Plugin {plugin_id} does not have method {method_name}")
        
        method = getattr(plugin, method_name)
        return method(*args, **kwargs)
    
    def validate_plugin_manifest(self, manifest_path: str) -> Tuple[bool, List[str]]:
        """Validate a plugin manifest file"""
        errors = []
        
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
        except Exception as e:
            return False, [f"Invalid JSON: {e}"]
        
        # Required fields
        required_fields = ['id', 'name', 'version', 'author', 'description', 'type']
        for field in required_fields:
            if field not in manifest:
                errors.append(f"Missing required field: {field}")
        
        # Validate plugin type
        if 'type' in manifest:
            try:
                PluginType(manifest['type'])
            except ValueError:
                errors.append(f"Invalid plugin type: {manifest['type']}")
        
        # Validate version format
        if 'version' in manifest:
            import re
            if not re.match(r'^\d+\.\d+\.\d+', manifest['version']):
                errors.append("Version must be in semver format (e.g., 1.0.0)")
        
        return len(errors) == 0, errors
    
    def get_plugin_marketplace_info(self) -> Dict[str, Any]:
        """Get information about available plugins in marketplace (future feature)"""
        # Placeholder for future marketplace integration
        return {
            'available_plugins': [],
            'featured_plugins': [],
            'categories': list(PluginType),
            'total_count': 0
        }


# Example plugin implementations

class SampleAnalyticsPlugin(AnalyticsPlugin):
    """Sample analytics plugin demonstrating the interface"""
    
    def get_info(self) -> PluginInfo:
        return PluginInfo(
            id="sample_analytics",
            name="Sample Analytics Plugin",
            version="1.0.0",
            author="Todo CLI Team",
            description="Demonstrates analytics plugin interface",
            plugin_type=PluginType.ANALYTICS
        )
    
    def initialize(self) -> bool:
        self.api.log("info", "Sample analytics plugin initialized")
        return True
    
    def cleanup(self):
        self.api.log("info", "Sample analytics plugin cleaned up")
    
    def analyze(self, todos: List[Todo]) -> Dict[str, Any]:
        """Simple analysis example"""
        total_todos = len(todos)
        completed_todos = len([t for t in todos if t.completed])
        overdue_todos = len([t for t in todos if t.is_overdue() and not t.completed])
        
        return {
            'total_tasks': total_todos,
            'completed_tasks': completed_todos,
            'overdue_tasks': overdue_todos,
            'completion_rate': (completed_todos / total_todos * 100) if total_todos > 0 else 0
        }
    
    def get_metrics(self, todos: List[Todo]) -> Dict[str, float]:
        """Get quantitative metrics"""
        analysis = self.analyze(todos)
        return {
            'completion_rate': analysis['completion_rate'],
            'overdue_ratio': (analysis['overdue_tasks'] / analysis['total_tasks'] * 100) 
                           if analysis['total_tasks'] > 0 else 0
        }


class SampleDashboardPlugin(DashboardPlugin):
    """Sample dashboard plugin"""
    
    def get_info(self) -> PluginInfo:
        return PluginInfo(
            id="sample_dashboard",
            name="Sample Dashboard Plugin",
            version="1.0.0", 
            author="Todo CLI Team",
            description="Demonstrates dashboard plugin interface",
            plugin_type=PluginType.DASHBOARD
        )
    
    def initialize(self) -> bool:
        # Register custom widget data sources
        custom_source = self.create_data_source("custom_metric")
        self.api.register_dashboard_widget(type(custom_source))
        return True
    
    def cleanup(self):
        pass
    
    def get_widget_types(self) -> List[str]:
        return ["custom_metric"]
    
    def create_data_source(self, widget_type: str) -> DataSource:
        if widget_type == "custom_metric":
            return CustomMetricDataSource()
        else:
            raise ValueError(f"Unknown widget type: {widget_type}")


class CustomMetricDataSource(DataSource):
    """Custom dashboard data source example"""
    
    def __init__(self):
        super().__init__("custom_metric")
    
    def fetch_data(self, params: Dict[str, Any]) -> WidgetData:
        todos = params.get('todos', [])
        
        # Example custom metric: tasks per project ratio
        projects = {}
        for todo in todos:
            project = todo.project or "No Project"
            projects[project] = projects.get(project, 0) + 1
        
        if projects:
            max_project = max(projects, key=projects.get)
            max_count = projects[max_project]
            total = sum(projects.values())
            ratio = (max_count / total * 100) if total > 0 else 0
            
            return WidgetData(
                value=ratio,
                label="Largest Project Ratio",
                unit="%",
                icon="📊",
                format=".1f",
                metadata={'project': max_project, 'count': max_count}
            )
        else:
            return WidgetData(value=0, label="Largest Project Ratio", unit="%")
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            'metric_name': {
                'type': 'text',
                'default': 'project_ratio',
                'label': 'Metric Name'
            }
        }