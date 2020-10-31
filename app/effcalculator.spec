# -*- mode: python ; coding: utf-8 -*-
import sys
sys.setrecursionlimit(5000)

PATHEX = os.path.abspath('')

block_cipher = None


a = Analysis(['effcalculator.py'],
             pathex=[PATHEX],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='effcalculator',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False, icon='effcalculator.ico' )

import shutil

files = ['dataset.json', 'configuration.json']
dirs = []
ignorefile = '.ignore'

def ignore(*args):
    dirname, names = args
    if ignorefile in names:
        names.remove(ignorefile)
        with open(os.path.join(dirname, '.ignore')) as f:
            for line in f:
                try:
                    names.remove(line.strip())
                except ValueError:
                    pass
    return dirname, names

for file in files:
    shutil.copyfile(file, os.path.join(PATHEX, 'dist', file))
for _dir in dirs:
    odir = os.path.join(PATHEX, 'dist', _dir)
    if os.path.isdir(odir):
        shutil.rmtree(odir)
    shutil.copytree(_dir, os.path.join(PATHEX, 'dist', _dir), ignore=ignore)
