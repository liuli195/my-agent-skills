#!/usr/bin/env python3
"""Prepare released tools/skills and dispatch existing project setup recipes.

Git, npm and each project's installer own installation. This entry records the
resolved versions, not another dependency solver. Paths are explicit so callers
can approve the writable root before running installation.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request


def run(args, *, cwd=None):
    return subprocess.run([str(x) for x in args], cwd=cwd, check=True,
                          text=True, stdout=subprocess.PIPE).stdout.strip()


def github(path):
    request = urllib.request.Request('https://api.github.com/' + path,
                                     headers={'User-Agent': 'cloud-bootstrap'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def link(path, target):
    if path.is_symlink() and path.resolve() == target.resolve():
        return
    if path.exists() or path.is_symlink():
        raise ValueError(f'Existing installation must be reviewed before replacement: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(target.resolve(), target_is_directory=target.is_dir())


def synchronize(manifest, root, latest, selected):
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / 'installed.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'sources': {}, 'npm': {}}
    state['pending'] = list(manifest.get('optional_skills', []))
    discovery = root / 'skills'
    discovery.mkdir(exist_ok=True)
    for item in manifest.get('sources', []):
        name, repo = item['name'], item['repo']
        if selected and name not in selected:
            continue
        previous = state['sources'].get(name, {})
        ref = item.get('ref')
        if not ref:
            ref = previous.get('ref') if not latest else None
            if not ref:
                if item.get('channel', 'release') == 'release':
                    ref = github(f'repos/{repo}/releases/latest')['tag_name']
                else:
                    ref = github(f'repos/{repo}/commits/HEAD')['sha']
        destination = root / 'sources' / name
        newly_cloned = not destination.exists()
        if newly_cloned:
            destination.parent.mkdir(parents=True, exist_ok=True)
            run(['git', 'clone', '--filter=blob:none', '--sparse', '--no-checkout',
                 f'https://github.com/{repo}.git', destination])
        if run(['git', '-C', destination, 'remote', 'get-url', 'origin']) != f'https://github.com/{repo}.git':
            raise ValueError(f'Unexpected source: {destination}')
        if run(['git', '-C', destination, 'status', '--porcelain']):
            # A fresh no-checkout clone has tracked deletions until first checkout.
            if previous:
                raise ValueError(f'Local changes in installation: {destination}')
        if newly_cloned or previous.get('ref') != ref:
            revision = previous.get('commit', ref) if previous.get('ref') == ref else ref
            run(['git', '-C', destination, 'fetch', '--depth', '1', 'origin', revision])
            run(['git', '-C', destination, 'checkout', '--detach', 'FETCH_HEAD'])
        paths = item.get('paths', [])
        if paths:
            run(['git', '-C', destination, 'sparse-checkout', 'set', *paths])
        for requested in paths:
            if not (destination / requested).exists() and Path(requested).name not in manifest.get('optional_skills', []):
                raise ValueError(f'Required source directory absent: {repo}@{ref}/{requested}')
        commit = run(['git', '-C', destination, 'rev-parse', 'HEAD'])
        if previous.get('ref') == ref and previous.get('commit') != commit:
            raise ValueError(f'Installation commit changed outside update: {destination}')
        for skill in destination.rglob('SKILL.md'):
            if '.git' in skill.parts:
                continue
            link(discovery / skill.parent.name, skill.parent)
            if skill.parent.name in state['pending']:
                state['pending'].remove(skill.parent.name)
        state['sources'][name] = {'repo': repo, 'ref': ref, 'commit': commit}
        save(state_path, state)
    prefix = root / 'npm'
    for item in manifest.get('npm', []):
        name = item['name']
        if selected and name not in selected:
            continue
        version = item.get('version') or (state['npm'].get(name) if not latest else None)
        if not version:
            version = json.loads(run(['npm', 'view', name, 'version', '--json']))
        package = prefix / 'lib' / 'node_modules' / name
        installed = json.loads((package / 'package.json').read_text()) if (package / 'package.json').exists() else {}
        if installed.get('version') != version:
            run(['npm', 'install', '--global', '--prefix', prefix, '--cache', root / 'cache/npm',
                 '--ignore-scripts', '--no-audit', '--no-fund', f'{name}@{version}'])
        for skill in (package / 'skills').glob('*/SKILL.md'):
            link(discovery / skill.parent.name, skill.parent)
        state['npm'][name] = version
        save(state_path, state)
    obsolete = [str(path) for path in discovery.iterdir() if not (path/'SKILL.md').is_file()]
    if obsolete:
        raise ValueError('Review obsolete managed links before approved cleanup: ' + ', '.join(obsolete))
    state['pending'] = [name for name in manifest.get('optional_skills', []) if not (discovery/name/'SKILL.md').is_file()]
    save(state_path, state)
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'update'])
    parser.add_argument('--root', type=Path, required=True, help='Approved common installation directory')
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('cloud-environment.json'))
    parser.add_argument('--latest', action='store_true', help='Resolve latest releases for explicitly selected units')
    parser.add_argument('--only', action='append', default=[], help='Source group or npm package name')
    parser.add_argument('--project', type=Path, help='Run this repository\'s existing setup after common preparation')
    parser.add_argument('--skills-dir', type=Path, help='Approved user skill discovery directory')
    args = parser.parse_args(argv)
    try:
        if args.latest and (args.action != 'update' or not args.only):
            raise ValueError('--latest requires update --only NAME; project dependencies are never auto-upgraded')
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        names = {x['name'] for x in manifest.get('sources', []) + manifest.get('npm', [])}
        if set(args.only) - names:
            raise ValueError('Unknown update selection: ' + ', '.join(set(args.only) - names))
        root = args.root.expanduser().resolve()
        state = synchronize(manifest, root, args.latest, set(args.only))
        if args.skills_dir:
            for skill in (root / 'skills').iterdir():
                link(args.skills_dir.expanduser() / skill.name, skill)
        if args.project:
            project = args.project.resolve()
            remote = run(['git', '-C', project, 'remote', 'get-url', 'origin'])
            repository = remote.removesuffix('.git').replace('git@github.com:', '').removeprefix('https://github.com/')
            recipe = manifest.get('projects', {}).get(repository)
            if recipe is None:
                raise ValueError(f'Project not declared in common manifest: {repository}')
            if os.name == 'nt':
                command = recipe['windows_setup']
            else:
                command = [sys.executable, Path(__file__).with_name('project_environment.py'), '--project', project]
                for requirement in recipe['requirements']:
                    command.extend(['--requirement', requirement])
                if recipe.get('npm'):
                    command.append('--npm')
            print(run(command, cwd=project))
        print(json.dumps({'status': 'ready', 'root': str(root), 'pending': state['pending'],
                          'path': str(root/'npm/bin'), 'sources': state['sources'], 'npm': state['npm']}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError) and error.stdout:
            print(error.stdout, file=sys.stderr)
        print(f'Initialization failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
