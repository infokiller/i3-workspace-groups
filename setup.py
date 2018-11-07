import setuptools
import os
from setuptools import setup

readme_path = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), 'README.md')
with open(readme_path) as f:
    long_description = f.read()

setuptools.setup(
    name='i3-workspace-groups',
    version='0.1.6',
    description='Manage i3wm workspaces in groups you control',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/infokiller/i3-workspace-groups',
    author='infokiller',
    author_email='joweill@icloud.com',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Operating System :: POSIX :: Linux',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='i3 i3wm extensions add-ons',
    packages=setuptools.find_packages(),
    install_requires=['i3ipc'],
    scripts=[
        'scripts/i3-workspace-groups',
        'scripts/i3-assign-workspace-to-group',
        'scripts/i3-switch-active-workspace-group',
    ],
)
