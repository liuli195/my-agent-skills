#!/usr/bin/env python3
"""Linux project dependencies; Windows keeps its existing project setup recipe."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def dependency_identity(root, manifests):
    inputs = {}
    def visit(path):
        path = path.resolve()
        relative = str(path.relative_to(root.resolve()))
        if relative in inputs:
            return
        text = path.read_text(encoding='utf-8').replace('\r\n', '\n')
        inputs[relative] = hashlib.sha256(text.encode()).hexdigest()
        for line in text.splitlines():
            line = line.strip()
            for prefix in ('-r ', '--requirement ', '-c ', '--constraint '):
                if line.startswith(prefix):
                    visit(path.parent / line[len(prefix):].strip())
    for manifest in manifests:
        visit(root / manifest)
    return inputs


def run(command, root):
    subprocess.run([str(x) for x in command], cwd=root, check=True)


def prepare(root, recipe):
    requirements = recipe.get('requirements', [])
    manifests = requirements + (['package.json', 'package-lock.json'] if recipe.get('npm') else [])
    identity = {'inputs': dependency_identity(root, manifests),
                'python': f'{sys.version_info.major}.{sys.version_info.minor}'}
    if recipe.get('npm'):
        identity['node'] = subprocess.check_output(['node', '--version'], text=True).strip()
    common = Path(subprocess.check_output(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'],
                                         cwd=root, text=True).strip()).parent
    state_path = root / '.local/project-environment.json'
    if common.resolve() != root.resolve():
        shared_state = common / '.local/project-environment.json'
        if not shared_state.exists() or json.loads(shared_state.read_text()) != identity:
            raise ValueError('Shared environment is missing or differs; initialize the primary checkout first')
        for name in ['.venv'] + (['node_modules'] if recipe.get('npm') else []):
            target, link = common / name, root / name
            if not target.exists():
                raise ValueError(f'Missing shared environment: {target}')
            if link.is_symlink() and link.resolve() == target.resolve():
                continue
            if link.exists() or link.is_symlink():
                raise ValueError(f'Existing non-shared directory: {link}')
            link.symlink_to(target, target_is_directory=True)
        return 'reused'
    previous = json.loads(state_path.read_text()) if state_path.exists() else None
    python = root / '.venv/bin/python'
    if (root / '.venv').is_symlink():
        raise ValueError('Primary checkout must own its virtual environment')
    if python.exists():
        version = subprocess.check_output([str(python), '-c', 'import sys; print("%s.%s" % sys.version_info[:2])'], text=True).strip()
        if version != identity['python']:
            raise ValueError('Python version changed; approve rebuilding the existing virtual environment first')
    if previous == identity and python.exists() and (not recipe.get('npm') or (root/'node_modules').exists()):
        return 'reused'
    state_path.parent.mkdir(parents=True, exist_ok=True)
    # Invalidate success before installing so an interrupted update cannot claim reuse.
    if state_path.exists():
        state_path.unlink()
    if not python.exists():
        run([sys.executable, '-m', 'venv', root/'.venv'], root)
    if requirements:
        run([python, '-m', 'pip', 'install', '--disable-pip-version-check', '--cache-dir', root/'.local/pip-cache',
             *[arg for item in requirements for arg in ('-r', item)]], root)
    if recipe.get('npm'):
        run(['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund', '--cache', root/'.local/npm-cache'], root)
        (root/'node_modules').mkdir(exist_ok=True)
    state_path.write_text(json.dumps(identity, indent=2) + '\n', encoding='utf-8')
    return 'prepared'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path.cwd())
    parser.add_argument('--requirement', action='append', default=[])
    parser.add_argument('--npm', action='store_true')
    args = parser.parse_args(argv)
    try:
        if os.name == 'nt':
            raise ValueError('Use the existing Windows setup recipe')
        root = args.project.resolve()
        recipe = {'requirements': args.requirement, 'npm': args.npm}
        print(prepare(root, recipe))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
