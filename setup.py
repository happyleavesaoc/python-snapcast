from setuptools import setup
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name='snapcast',
    version='2.3.6',
    description='Control Snapcast.',
    url='https://github.com/happyleavesaoc/python-snapcast/',
    license='MIT',
    author='happyleaves',
    author_email='happyleaves.tfr@gmail.com',
    packages=['snapcast', 'snapcast.control', 'snapcast.client'],
    install_requires=[
        'construct>=2.5.2',
        'packaging',
    ],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ],
    long_description=long_description,
    long_description_content_type='text/markdown'
)
