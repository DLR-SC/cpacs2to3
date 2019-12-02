# cpacs2to3

[![Build Status](https://travis-ci.com/DLR-SC/cpacs2to3.svg?branch=master)](https://travis-ci.com/DLR-SC/cpacs2to3)

A tool to convert CPACS files from version 2 to CPACS 3.

## Quickstart
The simplest way to install cpacs2to3 is to use the conda package manager. The dependencies should be installed automatically and you should be ready to go:

	$ conda create -n cpacs2to3 python=3.5 cpacs2to3 -c dlr-sc 
	
Enter the virtual environment

	$ activate cpacs2to3

To convert a cpacs file, just call cpacs2to3 with the file to convert. 

	$ cpacs2to3 myaircraft.xml -o myaircraftv3.xml

If the output file is not specified, no file will be written, but the cpacs file will be printed to the standard out.

## What is converted at the moment?

 - Adds uIDs, that are required by the new CPACS 3 definition.
 - Conversion of the guide curve geometry. CPACS 3 uses a different definition of the guide curves, where we have to convert the geometry.
 - Conversion of the wing structure, including recomputation of eta/xsi coordinates to the new definition.
 - Increments the CPACS version number to 3.

## How does does it work?
We are using TiXI to transform the xml. This is the easy part. The hard part is the geometry conversion. To support this process, we use both the TiGL 2 and the TiGL 3 library that are able to compute the geometries for both cpacs standards.

## Development
cpacs2to3 requires tigl 2 and 3 in order to perform geometry conversions. The easiest way is to create a virtual conda environment 

	$ conda create -n cpacs2to3_devel python=3.5 tigl3 tigl tixi3 tixi -c dlr-sc

To enter this environment, enter

	$ activate cpacs2to3_devel

cpacs2to3 can then be installed into this environment using the standard `python setup.py install` command.

## Legal stuff
Copyright &copy; 2015-2016, German Aerospace Center (DLR e.V.)

This software is licensed under the Apache Public License 2.0. See `LICENSE` for details.
