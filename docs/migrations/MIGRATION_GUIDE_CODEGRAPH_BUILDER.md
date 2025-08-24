# Migration Guide: Refactored CodeGraph Builder

## Overview

The original `codegraph_builder.py` has been refactored into multiple focused components to improve maintainability, testability, and extensibility.

## File Structure Changes

### Before (1 file):

```
src/system/tools/
└── codegraph_builder.py (400+ lines)
```

### After (8 files):

```
src/system/tools/
├── codegraph_builder.py (100 lines - orchestration only)
├── config/
│   ├── __init__.py
│   └── builder_config.py (configuration management)
├── file_scanner.py (file discovery)
├── domain_mapper.py (domain/agent mapping)
├── entry_point_detector.py (entry point detection)
├── ast_utils.py (utility functions)
├── symbol_processor.py (AST node processing)
└── ast_analyzer.py (file parsing coordination)
```

## Key Changes

### 1. Configuration is Centralized

**Before**: Configuration scattered throughout the main class

```python
self.exclude_patterns = exclude_patterns or ["venv", ".venv", ...]
self.cli_entry_points = self._get_cli_entry_points()
# ... more config loading mixed with business logic
```

**After**: All configuration in one place

```python
config = BuilderConfig.from_project(root_path)
# All config loaded and validated in one step
```

### 2. Single Responsibility Classes

**Before**: One giant class doing everything

```python
class KnowledgeGraphBuilder:
    def scan_file(self):            # File parsing
    def _determine_domain(self):    # Domain mapping  
    def _get_cli_entry_points(self): # Config loading
    def _should_exclude_path(self): # File filtering
    # ... 20+ methods doing different things
```

**After**: Each class has one job

```python
class FileScanner:      # Only finds files
class DomainMapper:     # Only maps domains
class ASTAnalyzer:      # Only parses AST
class SymbolProcessor:  # Only processes symbols
```

### Benefits You'll Get

1. **Easier Debugging**
   When something breaks, you'll know exactly which component is failing:

   * File not found? → Check `FileScanner`
   * Wrong domain? → Check `DomainMapper`
   * AST parsing error? → Check `ASTAnalyzer`

2. **Faster Development**

   * Want to change how domains are mapped? Only modify `DomainMapper`.
   * Want to support new file types? Only modify `FileScanner`.

3. **Better Testing**
   Each component can be tested independently with simple unit tests.
