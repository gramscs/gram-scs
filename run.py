import importlib.util
import os
import socket
import subprocess
import sys
import venv
from pathlib import Path

os.environ.setdefault('FLASK_ENV', 'development')

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / '.venv'
REQUIREMENTS_FILE = PROJECT_ROOT / 'requirements.txt'
RUNTIME_IMPORTS = {
    'flask': 'Flask',
    'flask_limiter': 'Flask-Limiter',
    'flask_sqlalchemy': 'Flask-SQLAlchemy',
    'limits.storage': 'limits',
}


def _venv_python():
    if os.name == 'nt':
        return VENV_DIR / 'Scripts' / 'python.exe'
    return VENV_DIR / 'bin' / 'python'


def _missing_imports(python_executable=None):
    if python_executable is None:
        return [package for module, package in RUNTIME_IMPORTS.items() if importlib.util.find_spec(module) is None]

    check_script = (
        'import importlib.util, json; '
        f'imports = {RUNTIME_IMPORTS!r}; '
        'missing = [package for module, package in imports.items() if importlib.util.find_spec(module) is None]; '
        'print(json.dumps(missing))'
    )
    result = subprocess.run(
        [str(python_executable), '-c', check_script],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        return list(RUNTIME_IMPORTS.values())

    try:
        return __import__('json').loads(result.stdout or '[]')
    except Exception:
        return list(RUNTIME_IMPORTS.values())


def _install_requirements(python_executable, force_reinstall=False):
    if not REQUIREMENTS_FILE.exists():
        raise FileNotFoundError(f'Cannot install dependencies because {REQUIREMENTS_FILE} does not exist.')

    command = [str(python_executable), '-m', 'pip', 'install']
    if force_reinstall:
        command.append('--force-reinstall')
    command.extend(['-r', str(REQUIREMENTS_FILE)])
    subprocess.check_call(command)


def _ensure_local_runtime_environment():
    """Make `python run.py` work on a fresh checkout by using a project virtualenv."""
    missing = _missing_imports()
    if not missing:
        return

    venv_python = _venv_python()
    if not venv_python.exists():
        print('Creating local Python virtual environment in .venv ...')
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)

    # Always sync requirements before switching into the project virtualenv.
    # This repairs stale or partially installed environments, including missing
    # transitive packages that can otherwise surface as ModuleNotFoundError later.
    print('Ensuring Python dependencies from requirements.txt are installed ...')
    _install_requirements(venv_python)

    venv_missing = _missing_imports(venv_python)
    if venv_missing:
        print(
            'Repairing incomplete Python dependency installation for: '
            + ', '.join(venv_missing)
        )
        _install_requirements(venv_python, force_reinstall=True)
        venv_missing = _missing_imports(venv_python)
        if venv_missing:
            raise RuntimeError(
                'Python dependencies are still missing after reinstall: '
                + ', '.join(venv_missing)
            )

    if Path(sys.executable).resolve() != venv_python.resolve():
        print(f"Restarting with {venv_python} because the current Python is missing: {', '.join(missing)}")
        os.execv(str(venv_python), [str(venv_python), *sys.argv])


if __name__ == "__main__":
    _ensure_local_runtime_environment()

from app import create_app

app = create_app()


def _coerce_port(raw_port, default_port):
    raw_port = (raw_port or "").strip()
    if ":" in raw_port:
        raw_port = raw_port.rsplit(":", 1)[-1].strip()
    if raw_port.isdigit() and 1 <= int(raw_port) <= 65535:
        return int(raw_port)
    return default_port


def _find_available_port(start_port, host):
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]

if __name__ == "__main__":
    # Use debug mode only in development
    debug = os.getenv('FLASK_ENV') == 'development'
    host = os.getenv('HOST', '0.0.0.0')
    default_port = 5000 if debug else 10000
    requested_port = _coerce_port(os.getenv('PORT'), default_port)

    if os.getenv('PORT'):
        # Platforms such as Render route traffic only to their assigned PORT.
        # Never silently move to a different port in deployed environments.
        port = requested_port
    else:
        port = _find_available_port(requested_port, host)
        if port != requested_port:
            print(f"Requested port {requested_port} was busy; using {port} instead.")

    app.run(host=host, port=port, debug=debug)
