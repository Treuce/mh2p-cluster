"""Prepare a private SD copy of the pinned upstream Audi release.

Only unsigned Mods/root recovery files change. Data and Meta bytes are
preserved. Native/Java release binaries remain upstream, not our local port.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RELEASE_SHA = 'ee0ed7af7f96230e0181d9bd640b607c6520b31b6124267ea70a6decee8c59d7'
STOCK_SHA = '9d455b764854f7977971ae977b21fe7560d8a40cca86d31cb9c9a7f5821c0ecf'
UPD = 'Mods/ClusterIntegration/Update/'
GUIDE = '''# Audi MIB2p SD package — first diagnostic test

Prepared for the saved MH2p_ER_AUG35_P2873 firmware. This is the runnable
upstream v0034 Audi release with our verbose stock rollback scripts. It
DOES NOT contain our locally developed disconnect/reconnect or generation
changes: those need a matched ARM/QNX native and Java build. No replacement
Windows test executable is shipped. The first diagnostic pass installs the
mod's AA-only Java classes and GAL hook but disables cluster video injection
and map rendering. It is a real software modification, not passive logging.
The upstream e-tron report does not establish A6 compatibility.

## Copy to SD

Use an empty FAT32 SD card. Copy the CONTENTS of this folder to its root,
so Data/, Meta/, Mods/, Recovery/, failsafe.sh and this guide are directly
at the root. Do not add a root cluster_config.json or unrelated mods.
Keep the card and its original backup copy on the PC; recovery needs them.
To verify after copying, run VERIFY-CARD.ps1 from PowerShell on the PC:

    powershell -NoProfile -ExecutionPolicy Bypass -File X:\\VERIFY-CARD.ps1

Replace X: with your actual card drive. Run verification before changing
marker files or configuration. SHA256SUMS does not include itself or logs.

## Check recovery before installing

The supplied root failsafe.sh defaults to CHECK ONLY. With the existing
ModKit startup hook and this card inserted, a normal MMI restart should
produce Logs/ClusterIntegration-failsafe.log and numbered rollback logs.
The hook is started alongside normal services, so this does not prove it
finishes before Java starts. Do not deliberately break the MMI to test it.

Over the existing MMI SSH connection, using the actual card mount:

    ksh /fs/sda0/Mods/ClusterIntegration/Update/rollback.sh --check
    ksh /fs/sda0/Mods/ClusterIntegration/Update/rollback.sh --self-test

The card can instead be /fs/sdb0 or /fs/usb0_0. --self-test uses your actual
saved GAL bytes in an isolated directory on the SD and removes dummy mod
files there. It never mounts the app filesystem or signals live processes.
Expect CHECK_OK / SELFTEST_OK and EXIT_STATUS=0 in the numbered result.txt.
No working byte/digest comparison tool means installation is blocked.
Resolve that tool limitation before installing; do not bypass it.

## Diagnostic installation

diag.txt, config_overrides.txt and the packaged config disable map video.
gal_env.txt enables native logs without overriding diagnostic MERGE=0.
The AA-only JAR and Audi dependency stub are included; CarPlay is not opted
in and there is no force_install.txt. The native/Java binaries are preserved
from the pinned upstream release. Our receiver generation patch is absent.

Use the existing MH2p ModKit SD update procedure. Merely inserting the card
does not install the package. An installer log is created under
Logs/ClusterIntegration/install-N/commands.log and rollback preflight has
its own rollback-N log. Each log records commands/branches and stderr;
result.txt contains the exit status. INSTALL_SCRIPT_COMPLETE means this
script finished, not that AA or cockpit rendering has passed a vehicle test.

Afterwards check normal MMI, Android Auto, stock maps and NavCompass first.
Connect the phone and request navigation while parked. Save the card Logs/
plus /tmp/gal_preload.log, /tmp/gal_cluster.log and the card's cluster.log.
Do not enable video until the diagnostic results have been reviewed.

## Restore stock functionality

If SSH works:

    ksh /fs/sda0/Mods/ClusterIntegration/Update/rollback.sh

For startup recovery, create an empty file at
Mods/ClusterIntegration/uninstall.txt on this card, insert it and perform
a normal MMI restart. The root failsafe sees that existing ModKit marker
and invokes rollback rather than a check. The same marker also selects
uninstall when running the ModKit update flow. No separate arm file is used.

Recovery restores GAL from the saved stock bytes supplied on this card,
verifies the installed copy, and removes this mod's added JARs/helpers after
verified pre-change backups. Stock JARs and NavCompass are retained. The
installed ClusterIntegration Persist entry is marked for uninstall, and
the card remains in uninstall mode to prevent accidental reinstallation.
There is no automatic reboot; restart the MMI normally to reload stock
Java classes after rollback. Recovery failures are logged and return nonzero.
Retain the logs if it does not finish. Recovery runs only if QNX mounts the
card and executes the installed hook, or if you invoke it over SSH/ModKit.
It cannot recover a unit which never reaches that execution path.

Detailed script behaviour: Recovery/RECOVERY_LOGGING.md.
Private saved GAL bytes are included. Do not publish this card package.
'''
VERIFY_PS = r'''$ErrorActionPreference = 'Stop'
$cardRoot = $PSScriptRoot
$cardPrefix = [IO.Path]::GetFullPath($cardRoot).TrimEnd([char]92) + [IO.Path]::DirectorySeparatorChar
$count = 0
foreach ($row in Get-Content -LiteralPath (Join-Path $cardRoot 'SHA256SUMS')) {
    if ($row -notmatch '^([0-9a-f]{64})  (.+)$') { throw 'Invalid checksum row' }
    $expectedHash = $Matches[1]
    $relativeName = $Matches[2]
    $targetFile = [IO.Path]::GetFullPath((Join-Path $cardRoot $relativeName))
    if (-not $targetFile.StartsWith($cardPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe checksum path' }
    $actualHash = (Get-FileHash -LiteralPath $targetFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) { throw "Checksum mismatch: $relativeName" }
    $count++
}
Write-Output "PASS: $count SD files verified."
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(raw):
    name = raw.replace('\\', '/')
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or ':' in name:
        raise ValueError(f'Unsafe ZIP entry: {raw}')
    return name


def validate_payload(payload, release, stock):
    protected = [name for name in release if name.startswith(('Data/', 'Meta/'))]
    for name in protected:
        assert payload[name] == release[name], f'Signed ModKit bytes changed: {name}'
    binaries = [name for name in release if name.endswith(('.jar', '.so')) or name == UPD + 'cluster']
    for name in binaries:
        assert payload[name] == release[name], f'Upstream binary changed: {name}'
    assert payload[UPD + 'Stock/gal.real'] == payload[UPD + 'Stock/gal.reference'] == stock
    config = json.loads(payload[UPD + 'cluster_config.json'])
    assert config['config']['enableMapRender'] is False
    assert 'Mods/ClusterIntegration/diag.txt' in payload
    for forbidden in ('Mods/ClusterIntegration/uninstall.txt', 'Mods/ClusterIntegration/enable_carplay.txt',
                      'Mods/ClusterIntegration/force_install.txt', 'cluster_config.json'):
        assert forbidden not in payload, forbidden
    aa_names = [n for n in binaries if '/aa_only/' in n]
    assert len(aa_names) == 1
    import io
    with zipfile.ZipFile(io.BytesIO(payload[aa_names[0]])) as jar:
        assert not any(n.startswith('de/audi/app/terminalmode/smartphone/carplay/') for n in jar.namelist())
        assert any(n.endswith('/AndroidAuto2EventListener.class') for n in jar.namelist())
    for name, data in payload.items():
        if name.endswith('.sh'):
            assert b'\r\n' not in data, name
    return dict(signed_files_unchanged=len(protected), upstream_binaries_unchanged=len(binaries),
                diagnostic_mode=True, contains_local_lifecycle_changes=False, car_tested=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release', type=Path, default=ROOT / 'builds/ClusterIntegration_v0034_beta2_candidate_90d0b76_audi.zip')
    p.add_argument('--stock-gal', type=Path, required=True)
    p.add_argument('--output-directory', type=Path, required=True)
    args = p.parse_args()
    release_data = args.release.read_bytes()
    assert sha(release_data) == RELEASE_SHA, 'Wrong upstream release ZIP'
    stock = args.stock_gal.read_bytes()
    assert sha(stock) == STOCK_SHA and stock[:4] == b'\x7fELF', 'Wrong saved stock GAL'
    release = {}
    with zipfile.ZipFile(args.release) as z:
        for entry in z.infolist():
            if entry.is_dir():
                continue
            name = safe_name(entry.filename)
            assert name not in release, name
            release[name] = z.read(entry)
    payload = dict(release)
    for source in sorted((ROOT / 'modkit/Mods').rglob('*')):
        if source.is_file():
            name = 'Mods/' + source.relative_to(ROOT / 'modkit/Mods').as_posix()
            data = source.read_bytes()
            payload[name] = data.replace(b'\r\n', b'\n') if source.suffix == '.sh' else data
    config = json.loads(payload[UPD + 'cluster_config.json'])
    config['config']['enableMapRender'] = False
    payload[UPD + 'cluster_config.json'] = (json.dumps(config, indent=2) + '\n').encode()
    payload['Mods/ClusterIntegration/diag.txt'] = b'diagnostic first pass\n'
    payload['Mods/ClusterIntegration/config_overrides.txt'] = b'enableMapRender=false\n'
    payload['Mods/ClusterIntegration/gal_env.txt'] = b'GAL_CLUSTER_LOG=1\nGAL_CLUSTER_LOG_ALL=1\nGAL_CLUSTER_LOG_DETAILS=1\nGAL_CLUSTER_SD_LOG=1\n'
    payload['failsafe.sh'] = (ROOT / 'modkit/sd_failsafe.sh').read_bytes().replace(b'\r\n', b'\n')
    payload[UPD + 'Stock/gal.real'] = stock
    payload[UPD + 'Stock/gal.reference'] = stock
    payload['Recovery/RECOVERY_LOGGING.md'] = (ROOT / 'modkit/RECOVERY_LOGGING.md').read_bytes().replace(b'\r\n', b'\n')
    payload['Recovery/upstream-README.md'] = release['README.md']
    payload['README.md'] = GUIDE.encode('utf-8')
    payload['VERIFY-CARD.ps1'] = VERIFY_PS.encode('utf-8')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    receipt = dict(schema=1, kind='upstream-audi-diagnostic-with-verbose-stock-rollback',
                   prepared_date='2026-10-14', firmware='MH2p_ER_AUG35_P2873',
                   script_commit=commit, upstream_commit='ae1b8fe3a6a679f33dee9a93ab7adf43772c83d0',
                   release_sha256=RELEASE_SHA, saved_gal_sha256=STOCK_SHA,
                   **validate_payload(payload, release, stock))
    payload['Recovery/package-provenance.json'] = (json.dumps(receipt, indent=2) + '\n').encode()
    payload['SHA256SUMS'] = ''.join(f'{sha(data)}  {name}\n' for name, data in sorted(payload.items())).encode('ascii')
    output = args.output_directory.resolve()
    # Never merge into an old SD folder which might contain arming markers.
    output.mkdir(parents=True, exist_ok=False)
    for name, data in sorted(payload.items()):
        dst = output / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        assert sha(dst.read_bytes()) == sha(data)
    archive = output.with_suffix('.zip')
    if archive.exists():
        raise FileExistsError(archive)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 14, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        final = {name: z.read(name) for name in z.namelist()}
        assert final == payload
        validate_payload(final, release, stock)
        for row in final['SHA256SUMS'].decode().splitlines():
            expected, name = row.split('  ', 1)
            assert sha(final[name]) == expected
    validation = dict(**receipt, sd_files=len(payload), zip_sha256=sha(archive.read_bytes()),
                      zip_bytes=archive.stat().st_size, zip=str(archive), directory=str(output))
    output.with_suffix('.validation.json').write_text(json.dumps(validation, indent=2) + '\n')
    print(json.dumps(validation, indent=2))


if __name__ == '__main__':
    main()
