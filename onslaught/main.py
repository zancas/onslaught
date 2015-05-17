import os
import sys
import argparse
import logging
import tempfile
import subprocess


DESCRIPTION = """\
Run the target python project through a battery of tests.
"""


def main(args = sys.argv[1:]):
    opts = parse_args(args)
    log = logging.getLogger('main')
    log.debug('Parsed opts: %r', opts)

    onslaught = Onslaught(opts.TARGET)

    onslaught.prepare_virtualenv()

    sdist = onslaught.create_sdist()
    onslaught.install('install-sdist', sdist)

    raise NotImplementedError(repr(main))


def parse_args(args):
    parser = argparse.ArgumentParser(description=DESCRIPTION)

    loggroup = parser.add_mutually_exclusive_group()

    loggroup.add_argument(
        '--quiet',
        action='store_const',
        const=logging.WARN,
        dest='loglevel',
        help='Only log warnings and errors.')

    loggroup.add_argument(
        '--debug',
        action='store_const',
        const=logging.DEBUG,
        dest='loglevel',
        help='Log everything.')

    parser.add_argument(
        'TARGET',
        type=str,
        nargs='?',
        default='.',
        help='Target python source.')

    opts = parser.parse_args(args)
    init_logging(opts.loglevel)
    return opts


LogFormatter = logging.Formatter(
    fmt='%(asctime)s %(levelname) 5s %(name)s | %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S%z')


def init_logging(level):
    if level is None:
        level = logging.INFO

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(LogFormatter)
    root.addHandler(handler)


class Onslaught (object):
    _TEST_DEPENDENCIES = [
        'twisted >= 14.0', # For trial
        'coverage == 3.7.1',
        ]

    def __init__(self, target):
        self._log = logging.getLogger(type(self).__name__)

        self._target = os.path.abspath(target)
        targetname = os.path.basename(self._target)
        self._basedir = tempfile.mkdtemp(prefix='onslaught.', suffix='.' + targetname)
        self._log.info('Onslaught results directory: %r', self._basedir)

        logpath = self._base_path('logs', 'main.log')
        self._logdir = os.path.dirname(logpath)

        os.mkdir(self._logdir)
        handler = logging.FileHandler(logpath)
        handler.setFormatter(LogFormatter)
        logging.getLogger().addHandler(handler)

        self._log.debug('Created debug level log in: %r', logpath)
        self._logstep = 0
        self._venv = self._base_path('venv')

    def prepare_virtualenv(self):
        self._log.info('Preparing virtualenv.')
        self._run('virtualenv', 'virtualenv', self._venv)

        for spec in self._TEST_DEPENDENCIES:
            name = spec.split()[0]
            logname = 'pip-install.{}'.format(name)
            self.install(logname, spec)

    def install(self, logname, spec):
        self._venv_run(logname, 'pip', '--verbose', 'install', spec)

    def create_sdist(self):
        setup = self._target_path('setup.py')
        distdir = self._base_path('dist')
        os.mkdir(distdir)
        self._venv_run(
            'setup-sdist',
            'python',
             setup,
            'sdist',
            '--dist-dir',
            distdir)
        [distname] = os.listdir(distdir)
        sdist = os.path.join(distdir, distname)
        self._log.info('Testing generated sdist: %r', sdist)
        return sdist

    def _base_path(self, *parts):
        return os.path.join(self._basedir, *parts)

    def _target_path(self, *parts):
        return os.path.join(self._target, *parts)

    def _venv_run(self, logname, cmd, *args):
        venvpath = os.path.join(self._venv, 'bin', cmd)
        self._run(logname, venvpath, *args)

    def _run(self, logname, *args):
        logfile = 'step-{0}.{1}.log'.format(self._logstep, logname)
        self._logstep += 1

        logpath = os.path.join(self._logdir, logfile)
        self._log.debug('Running: %r; logfile %r', args, logfile)

        with file(logpath, 'w') as f:
            subprocess.check_call(args, stdout=f, stderr=subprocess.STDOUT)
