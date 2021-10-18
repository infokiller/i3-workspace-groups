import os

import setuptools

from i3wsgroups import __version__

README_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                           'README.md')
with open(README_PATH, encoding='utf-8') as f:
    LONG_DESCRIPTION = f.read()

setuptools.setup(
    name='i3-workspace-groups',
    version=__version__,
    description='Manage i3wm workspaces in groups you control',
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    url='https://github.com/infokiller/i3-workspace-groups',
    author='infokiller',
    author_email='gitinfokiller@gmail.com',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Operating System :: POSIX :: Linux',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    keywords='i3 i3wm extensions add-ons',
    packages=setuptools.find_packages(exclude=['tests']),
    package_data={'i3wsgroups': ['default_config.toml']},
    install_requires=['i3ipc ~= 2.2', 'toml ~= 0.10'],
    extras_require={
        'dev': [
            'pylint ~= 2.11',
            'yapf ~= 0.31',
            'virtualenv ~= 20.8',
            'tox ~= 3.24',
            # As of 2021-10-18, tests are done without conda
            # 'tox-conda ~= 0.8',
            'pytest ~= 6.2',
            'pytest-cov ~= 3.0',
            'pytype ~= 2021.10',
            'pip-tools ~= 6.4',
            'codecov ~= 2.1',
        ]
    },
    scripts=[
        'scripts/i3-assign-workspace-to-group',
        'scripts/i3-autoname-workspaces',
        'scripts/i3-focus-on-workspace',
        'scripts/i3-move-to-workspace',
        'scripts/i3-rename-workspace',
        'scripts/i3-select-workspace-group',
        'scripts/i3-switch-active-workspace-group',
        'scripts/i3-workspace-groups',
        'scripts/i3-groups-polybar-module',
        'scripts/i3-groups-polybar-module-updater',
    ],
)
