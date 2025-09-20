"""Configuration management for the Todo CLI application."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import yaml

from .todo import Priority


@dataclass 
class ConfigModel:
    """Global configuration model for Todo CLI."""
    
    # Default settings
    default_project: str = "inbox"
    default_priority: Priority = Priority.MEDIUM
    default_view: str = "dashboard"  # dashboard, list, pinned, etc.
    
    # Display preferences
    show_completed: bool = True
    show_archived: bool = False
    max_completed_days: int = 30  # Only show completed tasks from last N days
    
    # Date preferences
    date_format: str = "%Y-%m-%d"
    time_format: str = "%H:%M"
    first_day_of_week: int = 0  # 0=Monday, 6=Sunday
    
    # Behavior settings
    auto_archive_completed: bool = False
    auto_archive_days: int = 30
    confirm_deletion: bool = True
    
    # Integration settings
    sync_enabled: bool = False
    sync_provider: Optional[str] = None  # "github", "dropbox", etc.
    sync_config: Dict[str, Any] = field(default_factory=dict)
    
    # Custom fields and extensions
    custom_contexts: List[str] = field(default_factory=list)  # Custom @contexts
    custom_priorities: List[str] = field(default_factory=list)  # Additional priorities
    plugins: List[str] = field(default_factory=list)  # Plugin names
    
    # File paths
    data_dir: str = "~/.todo"
    backup_dir: str = "~/.todo/backups"
    
    # UI and accessibility
    no_color: bool = False
    use_emoji: bool = True
    table_style: str = "rich"  # rich, simple, ascii
    
    def __post_init__(self):
        """Post-initialization setup."""
        # Expand user paths
        self.data_dir = os.path.expanduser(self.data_dir)
        self.backup_dir = os.path.expanduser(self.backup_dir)
        
        # Ensure directories exist
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.backup_dir).mkdir(parents=True, exist_ok=True)
        Path(self.data_dir, "projects").mkdir(parents=True, exist_ok=True)
    
    def to_yaml(self) -> str:
        """Serialize config to YAML."""
        data = {
            "default_project": self.default_project,
            "default_priority": self.default_priority.value if isinstance(self.default_priority, Priority) else self.default_priority,
            "default_view": self.default_view,
            "show_completed": self.show_completed,
            "show_archived": self.show_archived,
            "max_completed_days": self.max_completed_days,
            "date_format": self.date_format,
            "time_format": self.time_format,
            "first_day_of_week": self.first_day_of_week,
            "auto_archive_completed": self.auto_archive_completed,
            "auto_archive_days": self.auto_archive_days,
            "confirm_deletion": self.confirm_deletion,
            "sync_enabled": self.sync_enabled,
            "sync_provider": self.sync_provider,
            "sync_config": self.sync_config,
            "custom_contexts": self.custom_contexts,
            "custom_priorities": self.custom_priorities,
            "plugins": self.plugins,
            "data_dir": self.data_dir,
            "backup_dir": self.backup_dir,
            "no_color": self.no_color,
            "use_emoji": self.use_emoji,
            "table_style": self.table_style,
        }
        return yaml.dump(data, default_flow_style=False)
    
    @classmethod
    def from_yaml(cls, yaml_str: str) -> "ConfigModel":
        """Deserialize config from YAML."""
        data = yaml.safe_load(yaml_str)
        
        # Convert priority string back to enum if needed
        if "default_priority" in data and isinstance(data["default_priority"], str):
            try:
                data["default_priority"] = Priority(data["default_priority"])
            except ValueError:
                data["default_priority"] = Priority.MEDIUM
        
        return cls(**data)
    
    def get_project_path(self, project_name: str) -> Path:
        """Get the file path for a project."""
        return Path(self.data_dir) / "projects" / f"{project_name}.md"
    
    def get_config_path(self) -> Path:
        """Get the config file path."""
        return Path(self.data_dir) / "config.yaml"
    
    def get_backup_path(self, timestamp: Optional[str] = None) -> Path:
        """Get backup directory path."""
        if timestamp:
            return Path(self.backup_dir) / timestamp
        return Path(self.backup_dir)


class Config:
    """Configuration manager for Todo CLI."""
    
    _instance: Optional[ConfigModel] = None
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> ConfigModel:
        """Load configuration from file or create default."""
        if cls._instance is not None:
            return cls._instance
        
        config = ConfigModel()
        
        if config_path is None:
            config_path = config.get_config_path()
        
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    yaml_content = f.read()
                config = ConfigModel.from_yaml(yaml_content)
                print(f"Loaded configuration from {config_path}")
            except Exception as e:
                print(f"Warning: Failed to load config from {config_path}: {e}")
                print("Using default configuration.")
        else:
            # Create default config file
            cls.save(config, config_path)
            print(f"Created default configuration at {config_path}")
        
        cls._instance = config
        return config
    
    @classmethod
    def save(cls, config: ConfigModel, config_path: Optional[Path] = None) -> None:
        """Save configuration to file."""
        if config_path is None:
            config_path = config.get_config_path()
        
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(config_path, 'w') as f:
                f.write(config.to_yaml())
            print(f"Configuration saved to {config_path}")
        except Exception as e:
            print(f"Error: Failed to save config to {config_path}: {e}")
    
    @classmethod
    def get(cls) -> ConfigModel:
        """Get the current configuration instance."""
        if cls._instance is None:
            cls._instance = cls.load()
        return cls._instance
    
    @classmethod
    def reload(cls) -> ConfigModel:
        """Reload configuration from file."""
        cls._instance = None
        return cls.load()


def get_config() -> ConfigModel:
    """Get the current configuration."""
    return Config.get()


def load_config(config_path: Optional[Path] = None) -> ConfigModel:
    """Load configuration from file."""
    return Config.load(config_path)


def save_config(config: ConfigModel, config_path: Optional[Path] = None) -> None:
    """Save configuration to file."""
    Config.save(config, config_path)


def get_config_dir() -> Path:
    """Get the configuration directory path.
    
    Returns:
        Path to the configuration directory
    """
    config = get_config()
    return Path(config.data_dir)
