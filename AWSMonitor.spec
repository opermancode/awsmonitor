# PyInstaller spec for AWS Monitor (Windows GUI, no console)
# Build with: pyinstaller AWSMonitor.spec
block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['cryptography.hazmat.primitives.kdf.pbkdf2'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='AWSMonitor',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)
