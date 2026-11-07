#!/usr/bin/env python3
"""Prepare declared project dependencies using the existing platform recipe.

init and update synchronize declared dependencies; neither upgrades plugins nor
restores managed installation state.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def run(args, *, cwd=None):
    return subprocess.run([str(x) for x in args], cwd=cwd, check=True,
                          text=True, stdout=subprocess.PIPE).stdout.strip()


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ValueError('Environment manifest must be an object')
    unknown = set(manifest) - {'projects'}
    if unknown:
        raise ValueError('Unsupported environment manifest keys: ' + ', '.join(sorted(unknown)))
    projects = manifest.get('projects')
    if not isinstance(projects, dict):
        raise ValueError('Environment projects must be an object')
    for repository, recipe in projects.items():
        if not repository or not isinstance(recipe, dict):
            raise ValueError(f'Invalid project recipe: {repository}')
        unknown = set(recipe) - {'requirements', 'npm', 'windows_setup'}
        if unknown:
            raise ValueError(f'Unsupported project recipe keys for {repository}: ' + ', '.join(sorted(unknown)))
        requirements = recipe.get('requirements', [])
        if not isinstance(requirements, list) or any(not isinstance(item, str) or not item for item in requirements):
            raise ValueError(f'Project requirements must be a list of paths: {repository}')
        if not isinstance(recipe.get('npm', False), bool):
            raise ValueError(f'Project npm must be a boolean: {repository}')
        windows = recipe.get('windows_setup')
        if 'windows_setup' in recipe and (not isinstance(windows, list) or not windows or
                                        any(not isinstance(item, str) or not item for item in windows)):
            raise ValueError(f'Project windows_setup must be a nonempty command list: {repository}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('action', choices=['init', 'update'])
    parser.add_argument('--project', type=Path, required=True, help='Declared project directory')
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('cloud-environment.json'))
    args = parser.parse_args(argv)
    try:
        if sys.version_info[:2] != (3, 12):
            raise ValueError('Python 3.12 is required before preparing the environment')
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        validate_manifest(manifest)
        project = args.project.expanduser().resolve()
        remote = run(['git', '-C', project, 'remote', 'get-url', 'origin'])
        repository = remote.removesuffix('.git').replace('git@github.com:', '').removeprefix('https://github.com/')
        recipe = manifest.get('projects', {}).get(repository)
        if recipe is None:
            raise ValueError(f'Project not declared in environment manifest: {repository}')
        if os.name == 'nt':
            command = recipe['windows_setup']
        else:
            command = [sys.executable, Path(__file__).with_name('project_environment.py'), '--project', project]
            for requirement in recipe.get('requirements', []):
                command.extend(['--requirement', requirement])
            if recipe.get('npm'):
                command.append('--npm')
        print(run(command, cwd=project))
        print(json.dumps({'status': 'ready', 'project': str(project)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError) and error.stdout:
            print(error.stdout, file=sys.stderr)
        print(f'Initialization failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
