#!/usr/bin/env python3
"""
Code Quality Utilities - Tools for maintaining code quality.
"""

import os
import sys
import ast
import importlib
import pkgutil
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class FileMetrics:
    """Metrics for a single file."""
    path: str
    lines_total: int
    lines_code: int
    lines_comment: int
    lines_blank: int
    functions: int
    classes: int
    max_function_length: int
    complexity_estimate: int


@dataclass
class ModuleMetrics:
    """Metrics for a module/package."""
    name: str
    files: int
    total_lines: int
    avg_file_size: float
    largest_file: Tuple[str, int]
    public_api: List[str]


class CodeAnalyzer:
    """Analyzes code quality and structure."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self._file_metrics: Dict[str, FileMetrics] = {}
    
    def analyze_file(self, filepath: Path) -> FileMetrics:
        """Analyze a single Python file."""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
        
        # Count line types
        lines_total = len(lines)
        lines_blank = sum(1 for line in lines if not line.strip())
        lines_comment = sum(1 for line in lines if line.strip().startswith('#'))
        lines_code = lines_total - lines_blank - lines_comment
        
        # Parse AST for structure
        functions = 0
        classes = 0
        max_function_length = 0
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    functions += 1
                    func_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                    max_function_length = max(max_function_length, func_lines)
                elif isinstance(node, ast.ClassDef):
                    classes += 1
        except SyntaxError:
            pass
        
        # Simple complexity estimate
        complexity = (
            functions * 2 + 
            classes * 5 + 
            lines_code // 50 +
            max_function_length // 20
        )
        
        metrics = FileMetrics(
            path=str(filepath),
            lines_total=lines_total,
            lines_code=lines_code,
            lines_comment=lines_comment,
            lines_blank=lines_blank,
            functions=functions,
            classes=classes,
            max_function_length=max_function_length,
            complexity_estimate=complexity
        )
        
        self._file_metrics[str(filepath)] = metrics
        return metrics
    
    def analyze_directory(self, directory: Path) -> List[FileMetrics]:
        """Analyze all Python files in a directory."""
        results = []
        
        for filepath in directory.rglob('*.py'):
            if '__pycache__' not in str(filepath):
                try:
                    metrics = self.analyze_file(filepath)
                    results.append(metrics)
                except Exception as e:
                    print(f"Error analyzing {filepath}: {e}")
        
        return results
    
    def get_large_files(self, min_lines: int = 500) -> List[FileMetrics]:
        """Get files exceeding the line threshold."""
        return [m for m in self._file_metrics.values() 
                if m.lines_code >= min_lines]
    
    def get_complex_files(self, min_complexity: int = 50) -> List[FileMetrics]:
        """Get files with high complexity."""
        return [m for m in self._file_metrics.values() 
                if m.complexity_estimate >= min_complexity]
    
    def get_long_functions(self, min_lines: int = 50) -> List[FileMetrics]:
        """Get files with long functions."""
        return [m for m in self._file_metrics.values() 
                if m.max_function_length >= min_lines]


class ImportChecker:
    """Checks for import issues."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self._imports: Dict[str, Set[str]] = defaultdict(set)
    
    def extract_imports(self, filepath: Path) -> Set[str]:
        """Extract imports from a Python file."""
        imports = set()
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
        except Exception:
            pass
        
        return imports
    
    def build_import_graph(self, directory: Path) -> Dict[str, Set[str]]:
        """Build import dependency graph."""
        graph = {}
        
        for filepath in directory.rglob('*.py'):
            if '__pycache__' not in str(filepath):
                module_name = filepath.stem
                imports = self.extract_imports(filepath)
                graph[module_name] = imports
                self._imports[module_name] = imports
        
        return graph
    
    def find_circular_imports(self) -> List[Tuple[str, str]]:
        """Find potential circular imports."""
        circular = []
        
        for module, imports in self._imports.items():
            for imp in imports:
                if imp in self._imports:
                    if module in self._imports[imp]:
                        pair = tuple(sorted([module, imp]))
                        if pair not in circular:
                            circular.append(pair)
        
        return circular
    
    def find_unused_imports(self, filepath: Path) -> List[str]:
        """Find potentially unused imports in a file."""
        unused = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
            
            # Get all imported names
            imported_names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.asname or alias.name
                        imported_names.add(name)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        name = alias.asname or alias.name
                        imported_names.add(name)
            
            # Check if names are used
            for name in imported_names:
                if name not in ['*']:
                    # Simple check: count occurrences
                    count = content.count(name)
                    if count <= 1:  # Only in import
                        unused.append(name)
        
        except Exception:
            pass
        
        return unused


class CodeFormatter:
    """Utilities for code formatting."""
    
    @staticmethod
    def check_formatting(filepath: Path) -> Dict[str, Any]:
        """Check if file follows formatting standards."""
        issues = {
            'long_lines': [],
            'trailing_whitespace': [],
            'missing_docstring': False,
            'tab_indentation': []
        }
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines, 1):
                # Check line length
                if len(line.rstrip()) > 120:
                    issues['long_lines'].append(i)
                
                # Check trailing whitespace
                if line != line.rstrip() + '\n' and line.rstrip():
                    issues['trailing_whitespace'].append(i)
                
                # Check for tabs
                if '\t' in line:
                    issues['tab_indentation'].append(i)
            
            # Check for module docstring
            content = ''.join(lines)
            tree = ast.parse(content)
            if not ast.get_docstring(tree):
                issues['missing_docstring'] = True
                
        except Exception:
            pass
        
        return issues


def generate_report(base_path: Path) -> str:
    """Generate a comprehensive code quality report."""
    report = []
    report.append("=" * 60)
    report.append("DOSIDICUS CODE QUALITY REPORT")
    report.append("=" * 60)
    report.append("")
    
    # Analyze code
    analyzer = CodeAnalyzer(base_path)
    src_path = base_path / 'src'
    
    if src_path.exists():
        metrics = analyzer.analyze_directory(src_path)
        
        # Summary
        total_files = len(metrics)
        total_lines = sum(m.lines_total for m in metrics)
        total_code = sum(m.lines_code for m in metrics)
        total_functions = sum(m.functions for m in metrics)
        total_classes = sum(m.classes for m in metrics)
        
        report.append("SUMMARY")
        report.append("-" * 40)
        report.append(f"Total Files: {total_files}")
        report.append(f"Total Lines: {total_lines:,}")
        report.append(f"Lines of Code: {total_code:,}")
        report.append(f"Total Functions: {total_functions}")
        report.append(f"Total Classes: {total_classes}")
        report.append(f"Average File Size: {total_lines // max(1, total_files)} lines")
        report.append("")
        
        # Large files
        large_files = analyzer.get_large_files(min_lines=500)
        if large_files:
            report.append("LARGE FILES (>500 lines)")
            report.append("-" * 40)
            for m in sorted(large_files, key=lambda x: x.lines_code, reverse=True):
                name = Path(m.path).name
                report.append(f"  {name}: {m.lines_code} lines, {m.functions} functions")
            report.append("")
        
        # Complex files
        complex_files = analyzer.get_complex_files(min_complexity=50)
        if complex_files:
            report.append("COMPLEX FILES")
            report.append("-" * 40)
            for m in sorted(complex_files, key=lambda x: x.complexity_estimate, reverse=True)[:10]:
                name = Path(m.path).name
                report.append(f"  {name}: complexity={m.complexity_estimate}")
            report.append("")
        
        # Long functions
        long_func_files = analyzer.get_long_functions(min_lines=50)
        if long_func_files:
            report.append("FILES WITH LONG FUNCTIONS (>50 lines)")
            report.append("-" * 40)
            for m in sorted(long_func_files, key=lambda x: x.max_function_length, reverse=True):
                name = Path(m.path).name
                report.append(f"  {name}: max function length = {m.max_function_length} lines")
            report.append("")
    
    # Check imports
    import_checker = ImportChecker(base_path)
    if src_path.exists():
        import_checker.build_import_graph(src_path)
        circular = import_checker.find_circular_imports()
        
        if circular:
            report.append("POTENTIAL CIRCULAR IMPORTS")
            report.append("-" * 40)
            for pair in circular:
                report.append(f"  {pair[0]} <-> {pair[1]}")
            report.append("")
    
    report.append("=" * 60)
    report.append("END OF REPORT")
    report.append("=" * 60)
    
    return '\n'.join(report)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Code Quality Tool')
    parser.add_argument('--path', type=str, default='.', help='Project path')
    parser.add_argument('--report', action='store_true', help='Generate full report')
    parser.add_argument('--check-imports', action='store_true', help='Check imports')
    parser.add_argument('--analyze', type=str, help='Analyze specific file')
    
    args = parser.parse_args()
    base_path = Path(args.path).resolve()
    
    if args.report:
        print(generate_report(base_path))
    
    elif args.check_imports:
        checker = ImportChecker(base_path)
        src_path = base_path / 'src'
        if src_path.exists():
            checker.build_import_graph(src_path)
            circular = checker.find_circular_imports()
            if circular:
                print("Potential circular imports found:")
                for pair in circular:
                    print(f"  {pair[0]} <-> {pair[1]}")
            else:
                print("No circular imports detected.")
    
    elif args.analyze:
        analyzer = CodeAnalyzer(base_path)
        filepath = Path(args.analyze)
        if filepath.exists():
            metrics = analyzer.analyze_file(filepath)
            print(f"File: {filepath.name}")
            print(f"  Total Lines: {metrics.lines_total}")
            print(f"  Code Lines: {metrics.lines_code}")
            print(f"  Functions: {metrics.functions}")
            print(f"  Classes: {metrics.classes}")
            print(f"  Max Function Length: {metrics.max_function_length}")
            print(f"  Complexity: {metrics.complexity_estimate}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
