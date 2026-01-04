#!/usr/bin/env python3
"""
Deployment Script for Dosidicus
Handles building, packaging, and deployment tasks.
"""

import os
import sys
import shutil
import subprocess
import argparse
import platform
from pathlib import Path
from datetime import datetime


class DeploymentManager:
    """Manages deployment tasks for Dosidicus."""
    
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.dist_dir = self.project_root / 'dist'
        self.build_dir = self.project_root / 'build'
        self.version = self._get_version()
        self.platform_name = platform.system().lower()
    
    def _get_version(self) -> str:
        """Get version from pyproject.toml or version file."""
        try:
            pyproject = self.project_root / 'pyproject.toml'
            if pyproject.exists():
                with open(pyproject, 'r') as f:
                    for line in f:
                        if line.startswith('version'):
                            return line.split('=')[1].strip().strip('"\'')
        except Exception:
            pass
        return '3.0.0'
    
    def clean(self):
        """Clean build artifacts."""
        print("🧹 Cleaning build artifacts...")
        
        dirs_to_clean = [
            self.dist_dir,
            self.build_dir,
            self.project_root / '__pycache__',
            self.project_root / '.pytest_cache',
            self.project_root / '*.egg-info',
        ]
        
        for pattern in dirs_to_clean:
            for path in self.project_root.glob(str(pattern.name) if '*' in str(pattern) else ''):
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                    print(f"  Removed: {path}")
        
        # Also clean specified directories
        for d in [self.dist_dir, self.build_dir]:
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
                print(f"  Removed: {d}")
        
        print("✅ Clean complete")
    
    def install_deps(self, dev: bool = False):
        """Install dependencies."""
        print("📦 Installing dependencies...")
        
        cmd = [sys.executable, '-m', 'pip', 'install', '-e', '.']
        if dev:
            cmd.extend(['[dev]'])
        
        result = subprocess.run(cmd, cwd=self.project_root)
        
        if result.returncode == 0:
            print("✅ Dependencies installed")
        else:
            print("❌ Failed to install dependencies")
            sys.exit(1)
    
    def run_tests(self, coverage: bool = False):
        """Run test suite."""
        print("🧪 Running tests...")
        
        cmd = [sys.executable, '-m', 'pytest', 'tests/', '-v']
        if coverage:
            cmd.extend(['--cov=src', '--cov-report=html'])
        
        result = subprocess.run(cmd, cwd=self.project_root)
        
        if result.returncode == 0:
            print("✅ All tests passed")
        else:
            print("❌ Tests failed")
            sys.exit(1)
    
    def lint(self, fix: bool = False):
        """Run linting checks."""
        print("🔍 Running linting...")
        
        checks = [
            (['black', '--check', 'src/', 'plugins/'] if not fix else ['black', 'src/', 'plugins/']),
            (['isort', '--check-only', 'src/', 'plugins/'] if not fix else ['isort', 'src/', 'plugins/']),
            ['flake8', 'src/', 'plugins/', '--max-line-length=120', '--ignore=E501,W503'],
        ]
        
        for cmd in checks:
            print(f"  Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, cwd=self.project_root)
            if result.returncode != 0 and not fix:
                print(f"⚠️  {cmd[0]} found issues")
        
        print("✅ Linting complete")
    
    def build_executable(self):
        """Build standalone executable using PyInstaller."""
        print(f"🔨 Building executable for {self.platform_name}...")
        
        # Ensure PyInstaller is installed
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], 
                      capture_output=True)
        
        # Build command
        cmd = [
            sys.executable, '-m', 'PyInstaller',
            '--name', 'Dosidicus',
            '--windowed',
            '--add-data', f'images{os.pathsep}images',
            '--add-data', f'plugins{os.pathsep}plugins',
            '--add-data', f'brains{os.pathsep}brains',
            '--distpath', str(self.dist_dir),
            '--workpath', str(self.build_dir),
            'main.py'
        ]
        
        # Add icon if exists
        icon_path = self.project_root / 'images' / 'icon.ico'
        if icon_path.exists():
            cmd.extend(['--icon', str(icon_path)])
        
        result = subprocess.run(cmd, cwd=self.project_root)
        
        if result.returncode == 0:
            print(f"✅ Executable built in {self.dist_dir}")
        else:
            print("❌ Build failed")
            sys.exit(1)
    
    def package(self):
        """Package the build for distribution."""
        print("📦 Packaging for distribution...")
        
        app_dir = self.dist_dir / 'Dosidicus'
        if not app_dir.exists():
            print("❌ Build not found. Run build first.")
            sys.exit(1)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        archive_name = f'Dosidicus-{self.version}-{self.platform_name}-{timestamp}'
        
        if self.platform_name == 'windows':
            archive_path = self.dist_dir / f'{archive_name}.zip'
            shutil.make_archive(
                str(self.dist_dir / archive_name),
                'zip',
                self.dist_dir,
                'Dosidicus'
            )
        else:
            archive_path = self.dist_dir / f'{archive_name}.tar.gz'
            shutil.make_archive(
                str(self.dist_dir / archive_name),
                'gztar',
                self.dist_dir,
                'Dosidicus'
            )
        
        print(f"✅ Package created: {archive_path}")
        return archive_path
    
    def deploy_local(self):
        """Deploy to local installation."""
        print("🚀 Deploying locally...")
        
        if self.platform_name == 'windows':
            install_dir = Path(os.environ.get('LOCALAPPDATA', '')) / 'Dosidicus'
        else:
            install_dir = Path.home() / '.local' / 'share' / 'Dosidicus'
        
        source_dir = self.dist_dir / 'Dosidicus'
        
        if not source_dir.exists():
            print("❌ Build not found. Run build first.")
            sys.exit(1)
        
        # Remove old installation
        if install_dir.exists():
            shutil.rmtree(install_dir)
        
        # Copy new installation
        shutil.copytree(source_dir, install_dir)
        
        print(f"✅ Deployed to: {install_dir}")
    
    def full_deploy(self):
        """Run full deployment pipeline."""
        print("🚀 Starting full deployment pipeline...")
        print(f"   Version: {self.version}")
        print(f"   Platform: {self.platform_name}")
        print()
        
        self.clean()
        self.install_deps()
        self.run_tests()
        self.lint()
        self.build_executable()
        self.package()
        
        print()
        print("=" * 50)
        print("✅ Full deployment complete!")
        print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description='Dosidicus Deployment Tool')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Clean command
    subparsers.add_parser('clean', help='Clean build artifacts')
    
    # Install command
    install_parser = subparsers.add_parser('install', help='Install dependencies')
    install_parser.add_argument('--dev', action='store_true', help='Include dev dependencies')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Run tests')
    test_parser.add_argument('--coverage', action='store_true', help='Generate coverage report')
    
    # Lint command
    lint_parser = subparsers.add_parser('lint', help='Run linting')
    lint_parser.add_argument('--fix', action='store_true', help='Auto-fix issues')
    
    # Build command
    subparsers.add_parser('build', help='Build executable')
    
    # Package command
    subparsers.add_parser('package', help='Package for distribution')
    
    # Deploy command
    subparsers.add_parser('deploy', help='Deploy locally')
    
    # Full command
    subparsers.add_parser('full', help='Run full deployment pipeline')
    
    args = parser.parse_args()
    
    manager = DeploymentManager()
    
    if args.command == 'clean':
        manager.clean()
    elif args.command == 'install':
        manager.install_deps(dev=args.dev)
    elif args.command == 'test':
        manager.run_tests(coverage=args.coverage)
    elif args.command == 'lint':
        manager.lint(fix=args.fix)
    elif args.command == 'build':
        manager.build_executable()
    elif args.command == 'package':
        manager.package()
    elif args.command == 'deploy':
        manager.deploy_local()
    elif args.command == 'full':
        manager.full_deploy()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
