from setuptools import setup

setup(
    name='snapcast',
    version='1.2.0',
    description='Control Snapcast.',
    url='https://github.com/happyleavesaoc/python-snapcast/',
    license='MIT',
    author='happyleaves',
    author_email='happyleaves.tfr@gmail.com',
    packages=['snapcast', 'snapcast.client'],
    install_requires=[
        'construct>=2.5.2',
    ],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ]
)
