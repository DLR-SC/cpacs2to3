from setuptools import setup

setup(
    name='cpacs2to3',
    version='0.9',
    description='Converts CPACS 2 files to CPACS3 files',
    author='Martin Siggel',
    author_email=',martin.siggel@dlr.de',
    license='Apache-2.0',
    requires=['tigl3', 'tigl', 'tixi', 'semver', 'numpy'],
    packages=['cpacs2to3'],
    entry_points={
        'console_scripts': ['cpacs2to3 = cpacs2to3.cpacs_converter:main']}
)
