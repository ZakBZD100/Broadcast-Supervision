import os
import sys
import subprocess
import shutil


main_script = 'main.py'
icon_path = os.path.join('assets', 'Favicone', 'favicon.ico')

if not os.path.exists(main_script):
    print(f"Error: {main_script} not found.")
    sys.exit(1)
if not os.path.exists(icon_path):
    print(f"Error: {icon_path} not found.")
    sys.exit(1)

# add assets folder to bundle
assets_path = os.path.join('assets')
add_data = []
if os.path.exists(assets_path):
    add_data += ['--add-data', f'{assets_path}{os.pathsep}assets']

# add VLC plugins folder to bundle
plugins_path = os.path.join('plugins')
if os.path.exists(plugins_path):
    add_data += ['--add-data', f'{plugins_path}{os.pathsep}plugins']

cmd = [
    sys.executable, '-m', 'PyInstaller',
    '--onefile',
    '--windowed',
    f'--icon={icon_path}',
    '--add-binary', 'libvlc.dll;.',
    '--add-binary', 'libvlccore.dll;.',
] + add_data + [main_script]

print('Launching PyInstaller...')
res = subprocess.run(cmd)
if res.returncode == 0:
    print('Executable generated in dist/ folder.')
else:
    print('Error generating executable.') 