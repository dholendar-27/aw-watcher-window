import platform

block_cipher = None

a = Analysis(
    ["sd_watcher_window/__main__.py"],
    pathex=[],
    binaries=[("sd_watcher_window/sd-watcher-window-macos", "sd_watcher_window")] if platform.system() == "Darwin" else [],
    datas=[
        ("sd_watcher_window/printAppStatus.jxa", "sd_watcher_window"),
    ],
    hiddenimports=[],
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
    exclude_binaries=True,
    name="sd-watcher-window",
    debug=False,
    strip=False,
    upx=True,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="sd-watcher-window",
)
