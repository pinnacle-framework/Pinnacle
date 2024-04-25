import os
import subprocess
import sys
import time
import typing as t

SESSION_NAME = 'pinnacledb-local-cluster-session'


def create_tmux_session(session_name, commands):
    '''
    Create a tmux local cluster
    '''

    for ix, cmd in enumerate(commands, start=0):
        window_name = f'{session_name}:{ix}'
        run_tmux_command(['send-keys', '-t', window_name, cmd, 'C-m'])
        time.sleep(1)

    print('You can attach to the tmux session with:')
    print(f'tmux a -t {session_name}')


def run_tmux_command(command):
    print('tmux ' + ' '.join(command))
    subprocess.run(["tmux"] + command, check=True)


def up_cluster(notebook_token: t.Optional[str] = None):
    print('Starting the local cluster...')

    CFG = os.environ.get('pinnacleDB_CONFIG')
    assert CFG, 'Please set pinnacleDB_CONFIG environment variable'
    python_executable = sys.executable
    ray_path = os.popen('which ray').read().split('\n')[0].strip()
    ray_executable = os.path.join(os.path.dirname(python_executable), ray_path)
    run_tmux_command(
        [
            'new-session',
            '-d',
            '-s',
            SESSION_NAME,
        ]
    )

    run_tmux_command(['rename-window', '-t', f'{SESSION_NAME}:0', 'ray-head'])
    run_tmux_command(['new-window', '-t', f'{SESSION_NAME}:1', '-n', 'ray-worker'])
    run_tmux_command(['new-window', '-t', f'{SESSION_NAME}:2', '-n', 'vector-search'])
    run_tmux_command(['new-window', '-t', f'{SESSION_NAME}:3', '-n', 'cdc'])
    run_tmux_command(['new-window', '-t', f'{SESSION_NAME}:4', '-n', 'rest'])
    run_tmux_command(['new-window', '-t', f'{SESSION_NAME}:5', '-n', 'jupyter'])

    cmd = (
        f"pinnacleDB_CONFIG={CFG} PYTHONPATH=$(pwd):. {ray_executable} start"
        " --head --dashboard-host=0.0.0.0 --disable-usage-stats --block"
    )
    run_tmux_command(['send-keys', '-t', 'ray-head', cmd, 'C-m'])
    time.sleep(10)
    cmd = (
        f"pinnacleDB_CONFIG={CFG} "
        "RAY_ENABLE_WINDOWS_OR_OSX_CLUSTER=1 PYTHONPATH=$(pwd)"
        ":. {ray_executable} start --address=localhost:6379  --block"
    )
    run_tmux_command(['send-keys', '-t', 'ray-worker', cmd, 'C-m'])
    cmd = f"pinnacleDB_CONFIG={CFG} {python_executable} -m pinnacledb vector-search"
    run_tmux_command(['send-keys', '-t', 'vector-search', cmd, 'C-m'])
    cmd = f"pinnacleDB_CONFIG={CFG} {python_executable} -m pinnacledb cdc"
    run_tmux_command(['send-keys', '-t', 'cdc', cmd, 'C-m'])
    cmd = f"pinnacleDB_CONFIG={CFG} {python_executable} -m pinnacledb rest"
    run_tmux_command(['send-keys', '-t', 'rest', cmd, 'C-m'])
    cmd = (
        f"pinnacleDB_CONFIG={CFG} {python_executable} -m jupyter notebook "
        f"--no-browser --ip=0.0.0.0 --NotebookApp.token={notebook_token} --allow-root"
        if notebook_token
        else (
            f"pinnacleDB_CONFIG={CFG} {python_executable} -m "
            "jupyter notebook --no-browser --ip=0.0.0.0"
        )
    )
    run_tmux_command(['send-keys', '-t', 'jupyter', cmd, 'C-m'])

    print('You can attach to the tmux session with:')
    print(f'tmux a -t {SESSION_NAME}')
    print(f'local cluster started with tmux session {SESSION_NAME}')


def down_cluster():
    print('Stopping the local cluster...')
    run_tmux_command(['kill-session', '-t', SESSION_NAME])
    print('local cluster stopped')


def attach_cluster():
    run_tmux_command(['attach-session', '-t', SESSION_NAME])
