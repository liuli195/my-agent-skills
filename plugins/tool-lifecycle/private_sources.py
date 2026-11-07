"""Private source projection: pinned archives only; never part of a public Git tree."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import urllib.request
import zipfile

LIMIT = 20_000_000


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(value):
    p = PurePosixPath(value)
    if not p.parts or p.is_absolute() or '..' in p.parts or '\\' in value or ':' in value or p.as_posix() != value:
        raise ValueError('unsafe private source path')
    return p


def adapt_boolean(raw, rule):
    """Replace one unambiguous Boolean token, preserving every other byte."""
    field = rule['field']
    before, after = rule['before'], rule['after']
    if not field or len(field) > 2 or any(not re.fullmatch(r'[a-z_-]+', x) for x in field):
        raise ValueError('invalid Boolean field path')
    if type(before) is not bool or type(after) is not bool or before == after:
        raise ValueError('invalid Boolean adaptation')
    start, end = 0, len(raw)
    if rule['path'].endswith('/SKILL.md'):
        front = re.match(rb'---\r?\n(.*?)\r?\n---(?:\r?\n|$)', raw, re.S)
        if front is None: raise ValueError('missing skill frontmatter')
        start, end = front.span(1)
    block = raw[start:end]
    if len(field) == 2:
        parents = list(re.finditer(rb'^' + field[0].encode() + rb':[ \t]*\r?$', block, re.M))
        if len(parents) != 1: raise ValueError('ambiguous Boolean parent')
        a = parents[0].end()
        following = re.search(rb'\n[^ \t\r\n#]', block[a:])
        b = a + following.start() if following else len(block)
        start += a; block = block[a:b]
    matches = list(re.finditer(rb'^([ \t]*' + field[-1].encode() + rb':[ \t]*)(true|false)([ \t]*(?:#[^\r\n]*)?\r?)$', block, re.M))
    if len(matches) != 1 or matches[0][2].decode() != str(before).lower():
        raise ValueError('Boolean field absent, duplicated or changed')
    match = matches[0]; a, b = match.span(2)
    return raw[:start+a] + str(after).lower().encode() + raw[start+b:]


def project_archive(raw, config):
    if len(raw) > LIMIT or digest(raw) != config['archiveSha256']:
        raise ValueError('private source archive digest or size mismatch')
    if not re.fullmatch('[0-9a-f]{40}', config['commit']): raise ValueError('unpinned upstream commit')
    prefix = config['archivePrefix']; safe_path(prefix.rstrip('/'))
    files = {}; total = len(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for item in archive.infolist():
            safe_path(item.filename.rstrip('/'))
            if not item.filename.startswith(prefix) or item.filename == prefix: continue
            name = item.filename[len(prefix):]; safe_path(name.rstrip('/'))
            selected_roots = [x.removeprefix('./')+'/' for x in config['skills']]
            if name not in (config['manifest'], config['license']['path']) and not any(name.startswith(root) for root in selected_roots):
                continue  # Never extract unrelated upstream development files or links.
            mode = item.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise ValueError('unsupported upstream file type')
            total += item.file_size
            if total > LIMIT: raise ValueError('private source exceeds expanded budget')
            if item.is_dir(): continue
            if name in files: raise ValueError('duplicate upstream file')
            files[name] = archive.read(item)
    upstream = json.loads(files[config['manifest']])
    skills = config['skills']
    if not skills or len(skills) != len(set(skills)) or upstream['skills'] != skills or upstream['version'] != config['version']:
        raise ValueError('upstream official set or version changed')
    roots = [safe_path(x.removeprefix('./')).as_posix() for x in skills]
    if len({PurePosixPath(x).name for x in roots}) != len(roots): raise ValueError('duplicate skill identity')
    for root in roots:
        if root+'/SKILL.md' not in files: raise ValueError('official skill missing')
    license = config['license']; safe_path(license['path'])
    if digest(files[license['path']]) != license['sha256']: raise ValueError('upstream license mismatch')
    projected = {name: data for name, data in files.items() if name == license['path'] or any(name.startswith(root+'/') for root in roots)}
    original = dict(projected); changed = set()
    for rule in config['adaptations']:
        key = (rule['path'], tuple(rule['field']))
        if key in changed or rule['path'] not in projected: raise ValueError('invalid or duplicate adaptation')
        changed.add(key); projected[rule['path']] = adapt_boolean(projected[rule['path']], rule)
    provenance = {key:config[key] for key in ('repository','commit','version','archiveSha256','license')}
    provenance.update(originalFiles={k:digest(v) for k,v in original.items()}, adaptations=config['adaptations'])
    return projected, provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--archive-directory', type=Path)
    args = parser.parse_args(argv)
    project, output = args.project.resolve(), args.output.resolve()
    if output.is_relative_to(project) or project.is_relative_to(output):
        parser.error('private output and source tree must be disjoint')
    config_path = project / '.release-flow/private-sources.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    if config['version'] != 1: raise ValueError('private sources schema mismatch')
    path = output / 'snapshots.json'; manifest = json.loads(path.read_text(encoding='utf-8'))
    records = list(manifest['plugins'].values())
    if not records: raise ValueError('formal own snapshots required first')
    source = records[0]
    import subprocess
    def git(*args):
        return subprocess.run(['git','-C',str(project),*args],check=True,capture_output=True,text=True,timeout=30).stdout.strip()
    if (git('status','--porcelain') or git('rev-parse','HEAD') != source['sourceCommit']
            or git('rev-parse',source['releaseRef']+'^{commit}') != source['sourceCommit']
            or any(r.get('accountMode') != 'RELEASE' or r['sourceCommit'] != source['sourceCommit'] for r in records)):
        raise ValueError('private projection requires clean matching formal source')
    for item in config['sources']:
        name = item['name']; safe_path(name)
        if '/' in name or name in manifest['plugins']: raise ValueError('private package identity conflict')
        if args.archive_directory:
            raw = (args.archive_directory / (name+'.zip')).read_bytes()
        else:
            expected = 'https://codeload.github.com/'+item['repository']+'/zip/'+item['commit']
            if item['archiveUrl'] != expected: raise ValueError('archive URL not pinned to official source')
            with urllib.request.urlopen(expected, timeout=30) as response: raw = response.read(LIMIT+1)
        files, upstream = project_archive(raw,item)
        cloud = {'name':name,'version':item['version'],'description':'Private adapted upstream skills','skills':item['skills']}
        files['.codex-plugin/plugin.json'] = (json.dumps(cloud,ensure_ascii=False,indent=2)+'\n').encode()
        identity = digest(json.dumps(upstream,sort_keys=True).encode())
        filename = name+'-'+identity[:20]+'.zip'; artifact = output/filename; directory = output/artifact.stem
        if directory.exists() or artifact.exists(): raise ValueError('private output already exists; inspect before retry')
        directory.mkdir()
        with zipfile.ZipFile(artifact,'w',zipfile.ZIP_DEFLATED) as archive:
            for relative,data in sorted(files.items()):
                destination=directory/relative; destination.parent.mkdir(parents=True,exist_ok=True); destination.write_bytes(data)
                archive.writestr(relative,data)
        manifest['plugins'][name] = {**{k:source[k] for k in ('sourceCommit','sourceDirty','accountMode','releaseRef')},
            'packageName':name,'version':item['version'],'inputVersion':identity,'artifact':filename,'sha256':digest(artifact.read_bytes()),
            'sizeBytes':artifact.stat().st_size,'pluginPath':str(directory),'metadataSource':{'repository':source['metadataSource']['repository']},'upstream':upstream}
    temporary=path.with_suffix('.private.tmp');temporary.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temporary.replace(path)
    print(json.dumps({'status':'packaged','manifest':str(path),'runtimeVerification':'pending'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
