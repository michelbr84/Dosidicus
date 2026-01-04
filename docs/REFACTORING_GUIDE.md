# Dosidicus Code Refactoring Guide

This document provides guidelines for refactoring large files and maintaining code quality.

---

## Current Code Analysis

### Large Files (>1000 lines)

| File | Lines | Recommended Action |
|------|-------|-------------------|
| `brain_widget.py` | 5121 | Split into components |
| `brain_tool.py` | 3448 | Extract utilities |
| `tamagotchi_logic.py` | 3228 | Modularize by feature |
| `squid.py` | 2349 | Extract behaviors |
| `ui.py` | 1759 | Componentize UI |
| `designer_window.py` | 1533 | Extract panels |
| `designer_canvas.py` | 1261 | Extract tools |
| `preferences.py` | 1241 | Split by category |
| `neurogenesis.py` | 1119 | OK (focused module) |

---

## Refactoring Priorities

### Phase 1: Critical Files

#### `brain_widget.py` → Multiple Modules

Current structure (5121 lines):
- Visualization
- Editing
- Learning
- State management
- Animation

**Proposed split:**
```
src/brain/
├── __init__.py          # Exports main BrainWidget
├── widget.py            # Main BrainWidget class (~1000 lines)
├── visualization.py     # Rendering and drawing (~1200 lines)
├── editor.py            # Edit mode functionality (~800 lines)
├── learning.py          # Learning algorithms (~600 lines)
├── state.py             # State management (~500 lines)
└── animation.py         # Animation handling (~500 lines)
```

#### `tamagotchi_logic.py` → Feature Modules

Current structure (3228 lines):
- Game state
- Squid management
- Plugins
- Save/Load
- Statistics

**Proposed split:**
```
src/game/
├── __init__.py
├── logic.py             # Core game logic (~800 lines)
├── state.py             # Game state management (~500 lines)
├── plugin_manager.py    # Plugin handling (~400 lines)
├── persistence.py       # Save/load (~600 lines)
└── statistics.py        # Stats tracking (~400 lines)
```

---

## Refactoring Patterns

### 1. Extract Class

When a class has too many responsibilities:

```python
# Before
class BigClass:
    def method_a(self): ...
    def method_b(self): ...
    def method_c(self): ...  # Related to method_a, method_b
    def method_x(self): ...
    def method_y(self): ...  # Related to method_x

# After
class FeatureA:
    def method_a(self): ...
    def method_b(self): ...
    def method_c(self): ...

class FeatureX:
    def method_x(self): ...
    def method_y(self): ...

class BigClass:
    def __init__(self):
        self.feature_a = FeatureA()
        self.feature_x = FeatureX()
```

### 2. Extract Module

When functions are logically grouped:

```python
# Before: all in one file
def validate_neuron(n): ...
def validate_connection(c): ...
def validate_weight(w): ...
def render_neuron(n): ...
def render_connection(c): ...

# After: separate modules
# validators.py
def validate_neuron(n): ...
def validate_connection(c): ...
def validate_weight(w): ...

# renderers.py
def render_neuron(n): ...
def render_connection(c): ...
```

### 3. Extract Strategy

When behavior varies based on type:

```python
# Before
def process(item):
    if item.type == 'A':
        # 50 lines of A processing
    elif item.type == 'B':
        # 50 lines of B processing
    elif item.type == 'C':
        # 50 lines of C processing

# After
class ProcessorA:
    def process(self, item): ...

class ProcessorB:
    def process(self, item): ...

PROCESSORS = {'A': ProcessorA(), 'B': ProcessorB()}

def process(item):
    return PROCESSORS[item.type].process(item)
```

---

## Code Quality Checklist

### Before Refactoring

- [ ] Write tests for existing functionality
- [ ] Document current behavior
- [ ] Identify dependencies
- [ ] Create backup/commit

### During Refactoring

- [ ] Move one piece at a time
- [ ] Run tests after each change
- [ ] Update imports immediately
- [ ] Keep functionality identical

### After Refactoring

- [ ] All tests pass
- [ ] No circular imports
- [ ] Documentation updated
- [ ] Performance unchanged

---

## Module Dependencies

```
                ┌─────────────────┐
                │    main.py      │
                └────────┬────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌───────────┐    ┌───────────┐    ┌───────────┐
│    ui     │    │   logic   │    │  plugins  │
└─────┬─────┘    └─────┬─────┘    └─────┬─────┘
      │                │                │
      │    ┌───────────┼───────────┐    │
      │    │           │           │    │
      ▼    ▼           ▼           ▼    ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│    brain     │ │   squid  │ │  multiplayer │
└──────────────┘ └──────────┘ └──────────────┘
```

---

## Import Guidelines

### Prefer Relative Imports Within Package

```python
# Good
from .visualization import BrainVisualizer
from .editor import BrainEditor

# Avoid
from src.brain.visualization import BrainVisualizer
```

### Use `__init__.py` for Public API

```python
# brain/__init__.py
from .widget import BrainWidget
from .state import BrainState

__all__ = ['BrainWidget', 'BrainState']
```

### Avoid Circular Imports

```python
# Instead of importing class directly
from .other_module import OtherClass

# Use TYPE_CHECKING for type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .other_module import OtherClass
```

---

## Performance Considerations

### Lazy Loading

```python
# For heavy modules, use lazy loading
_heavy_module = None

def get_heavy_module():
    global _heavy_module
    if _heavy_module is None:
        from . import heavy_module
        _heavy_module = heavy_module
    return _heavy_module
```

### Caching

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_calculation(input_data):
    # Complex processing
    return result
```

---

## Testing After Refactoring

Run the full test suite:

```bash
python -m pytest tests/ -v
```

Check for import errors:

```bash
python -c "from src import *"
```

Verify no circular imports:

```bash
python scripts/check_imports.py
```

---

## Resources

- [Python Best Practices](https://docs.python-guide.org/)
- [Refactoring Guru](https://refactoring.guru/)
- [Clean Code in Python](https://github.com/zedr/clean-code-python)
