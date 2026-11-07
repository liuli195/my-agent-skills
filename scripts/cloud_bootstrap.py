#!/usr/bin/env python3
"""Prepare released tools/skills and dispatch existing project setup recipes.

Git, npm and each project's installer own installation. This entry records the
resolved versions, not another dependency solver. Paths are explicit so callers
can approve the writable root before running installation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
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


def native_discovery(manifest, state, root):
    """Keep approved native roots across init/update; never silently fall back."""
    replacements = {**state.get('discovery', {}), **manifest.get('discovery', {})}
    for name, item in replacements.items():
        path = Path(item['path']).expanduser()
        if path.name != 'SKILL.md' or not path.is_absolute() or path.resolve().is_relative_to((root / 'skills').resolve()):
            raise ValueError(f'Native skill must not use the retired managed discovery root: {name}')
        body = path.read_text(encoding='utf-8')
        frontmatter = body.split('---', 2)
        if len(frontmatter) != 3 or frontmatter[0].strip() or not re.search(
                r'^name:\s*[\'"]?' + re.escape(name) + r'[\'"]?\s*$', frontmatter[1], re.MULTILINE):
            raise ValueError(f'Native discovery identity is not verified: {name}: {path}')
        for resource in item['resources']:
            relative = Path(resource['path'])
            target = path.parent / relative
            if relative.is_absolute() or not target.resolve().is_relative_to(path.parent.resolve()):
                raise ValueError(f'Native skill resource escapes its root: {name}')
            if hashlib.sha256(target.read_bytes()).hexdigest() != resource['sha256']:
                raise ValueError(f'Native skill resource changed: {name}: {relative}')
    if replacements:
        state['discovery'] = replacements
    return replacements


def skill_path(root, state, name):
    item = state.get('discovery', {}).get(name)
    return Path(item['path']).expanduser().parent if item else root / 'skills' / name


def verify_runtime(manifest, supplied, managed):
    """Host-supplied official locations; never discover caches or reuse old state."""
    result = {'packages': {}, 'skills': {}, 'commands': {}}
    for declaration in manifest.get('runtime_packages', []):
        name = declaration['name']
        item = supplied.get('packages', {}).get(name)
        if not item or item.get('lifetime') not in ('installed', 'task') or item.get('channel') != 'RELEASE':
            raise ValueError(f'Required official runtime absent: {name}')
        root = Path(item['root']).expanduser()
        if not root.is_absolute() or any(root.resolve().is_relative_to(managed / folder) for folder in ('sources','npm','skills')):
            raise ValueError(f'Runtime must not use retired sources: {name}')
        if not item.get('pluginId') or not item.get('releaseId'):
            raise ValueError(f'Official runtime identity missing: {name}')
        metadata = json.loads((root / '.codex-plugin/plugin.json').read_text(encoding='utf-8'))
        if metadata['name'] != name or metadata['version'] != item['version'] or (declaration.get('version') and item['version'] != declaration['version']):
            raise ValueError(f'Runtime name or version mismatch: {name}')
        files = {path.relative_to(root).as_posix(): path for path in root.rglob('*') if path.is_file()}
        if set(files) != set(item['files']) or any(path.is_symlink() for path in root.rglob('*')):
            raise ValueError(f'Runtime complete inventory mismatch: {name}')
        for relative, path in files.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != item['files'][relative]:
                raise ValueError(f'Runtime file changed: {name}: {relative}')
        def resource(relative):
            target = root / relative
            if not target.resolve().is_relative_to(root.resolve()): raise ValueError('Runtime resource escapes package')
            return target
        for skill, relative in declaration.get('skills', {}).items():
            path = resource(relative) / 'SKILL.md'
            text = path.read_text(encoding='utf-8'); front = text.split('---', 2)
            if len(front) != 3 or front[0].strip() or not re.search(r'^name:\s*[\'"]?' + re.escape(skill) + r'[\'"]?\s*$',front[1],re.M):
                raise ValueError(f'Runtime skill identity mismatch: {skill}')
            if skill in result['skills']: raise ValueError('Duplicate runtime skill')
            result['skills'][skill] = str(path.parent)
        for command, relative in declaration.get('commands', {}).items():
            target = resource(relative)
            if not target.is_file() or command in result['commands']: raise ValueError('Invalid runtime command')
            result['commands'][command] = ['node',str(target)]
        result['packages'][name] = item
    return result


def synchronize(manifest, root, latest, selected):
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / 'installed.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'sources': {}, 'npm': {}}
    replacements = native_discovery(manifest, state, root)
    state['pending'] = list(manifest.get('optional_skills', []))
    state['exportedSkills'] = []
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
                ref = github(f'repos/{repo}/releases/latest')['tag_name']
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
            if skill.parent.name not in replacements:
                link(discovery / skill.parent.name, skill.parent)
                state['exportedSkills'].append(skill.parent.name)
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
            if skill.parent.name not in replacements:
                link(discovery / skill.parent.name, skill.parent)
                state['exportedSkills'].append(skill.parent.name)
        state['npm'][name] = version
        save(state_path, state)
    obsolete = [str(path) for path in discovery.iterdir() if not (path/'SKILL.md').is_file()]
    if obsolete:
        raise ValueError('Review obsolete managed links before approved cleanup: ' + ', '.join(obsolete))
    state['pending'] = [name for name in manifest.get('optional_skills', [])
                        if not (skill_path(root, state, name) / 'SKILL.md').is_file()]
    save(state_path, state)
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'update'])
    parser.add_argument('--root', type=Path, required=True, help='Approved common installation directory')
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('cloud-environment.json'))
    parser.add_argument('--runtime-manifest', type=Path, help='Verified current official package locations and complete inventories')
    parser.add_argument('--latest', action='store_true', help='Resolve latest releases for explicitly selected units')
    parser.add_argument('--only', action='append', default=[], help='Source group or npm package name')
    parser.add_argument('--project', type=Path, help='Run this repository\'s existing setup after common preparation')
    parser.add_argument('--skills-dir', type=Path, help='Approved user skill discovery directory')
    args = parser.parse_args(argv)
    try:
        if sys.version_info[:2] != (3, 12):
            raise ValueError('Python 3.12 is required before installing the environment')
        if args.latest and (args.action != 'update' or not args.only):
            raise ValueError('--latest requires update --only NAME; project dependencies are never auto-upgraded')
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        names = {x['name'] for x in manifest.get('sources', []) + manifest.get('npm', [])}
        if set(args.only) - names:
            raise ValueError('Unknown update selection: ' + ', '.join(set(args.only) - names))
        root = args.root.expanduser().resolve()
        supplied = json.loads(args.runtime_manifest.read_text(encoding='utf-8')) if args.runtime_manifest else {}
        runtime = verify_runtime(manifest, supplied, root)
        recipe = None
        if args.project:
            project = args.project.resolve()
            remote = run(['git', '-C', project, 'remote', 'get-url', 'origin'])
            repository = remote.removesuffix('.git').replace('git@github.com:', '').removeprefix('https://github.com/')
            recipe = manifest.get('projects', {}).get(repository)
            if recipe is None: raise ValueError(f'Project not declared in common manifest: {repository}')
            for binding in recipe.get('bindings', []):
                item = runtime['packages'].get(binding['package'])
                if not item or item['lifetime'] != 'installed':
                    raise ValueError('Project binding requires a persistent official runtime')
                target = Path(item['root']) / binding['script']
                if not target.resolve().is_relative_to(Path(item['root']).resolve()) or not target.is_file():
                    raise ValueError('Project runtime binding resource missing')
        state = synchronize(manifest, root, args.latest, set(args.only))
        if args.skills_dir:
            target_dir = args.skills_dir.expanduser()
            if target_dir.exists():
                obsolete = [str(path) for path in target_dir.iterdir()
                            if path.is_symlink() and path.resolve().is_relative_to(root)
                            and not (path/'SKILL.md').is_file()]
                if obsolete:
                    raise ValueError('Review obsolete user skill links before approved cleanup: ' + ', '.join(obsolete))
            for name in state['exportedSkills']:
                if name not in runtime['skills'] and name not in state.get('discovery', {}):
                    link(args.skills_dir.expanduser() / name, root / 'skills' / name)
        if args.project:
            if os.name == 'nt':
                command = recipe['windows_setup']
            else:
                command = [sys.executable, Path(__file__).with_name('project_environment.py'), '--project', project]
                for requirement in recipe['requirements']:
                    command.extend(['--requirement', requirement])
                if recipe.get('npm'):
                    command.append('--npm')
            print(run(command, cwd=project))
            for binding in recipe.get('bindings', []):
                package = runtime['packages'][binding['package']]
                implementation = Path(package['root']) / binding['script']
                if not implementation.resolve().is_relative_to(Path(package['root']).resolve()) or not implementation.is_file():
                    raise ValueError('Project binding script absent or outside runtime')
                if package['lifetime'] != 'installed':
                    raise ValueError('Stable project binding requires installed runtime; task resource cannot become a permanent link')
                for action in ('connect', 'check'):
                    print(run([sys.executable, implementation, action, '--project', project], cwd=project))
        state['runtime'] = runtime
        save(root / 'installed.json', state)
        print(json.dumps({'status': 'ready', 'root': str(root), 'pending': state['pending'],
                          'commands': runtime['commands'], 'public_npm_prefix': str(root/'npm'), 'sources': state['sources'], 'npm': state['npm'],
                          'runtime': runtime, 'discovery': state.get('discovery', {})}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError) and error.stdout:
            print(error.stdout, file=sys.stderr)
        print(f'Initialization failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
