from setuptools import setup
from distutils.extension import Extension


setup(
	name='cpacs2to3',
	version='0.1',
	description='Converts CPACS 2 files to CPACS3 files',
	author='Martin Siggel',
	author_email=',martin.siggel@dlr.de',
	license='Apache-2.0',
	requires=['tigl3', 'tigl', 'tixi'],
	packages=['cpacs2to3'],
	entry_points={
            'console_scripts': ['cpacs2to3 = cpacs2to3.cpacs_converter:main']}
)
