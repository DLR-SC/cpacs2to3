# cpacs2to3
A tool to convert CPACS files from version 2 to CPACS 3.

## Quickstart
Installation of cpacs2 follows the Python standard installation routine: Get the sources (e.g. using git) and run `setup.py install`. The dependencies should be installed automatically and you should be ready to go.

To convert a cpacs file, just call cpacs2to3 with the file to convert. 

	$ cpacs2to3 myaircraft.xml -o myaircraftv3.xml
	
If the output file is not specified, no file will be written, but the cpacs file will be printed to the standard out.

## What is converted at the moment?
Right now, only the required uiDs for e.g. transformations are added and the CPACS version number is incremented to 3.

## What should be converted, once this tool is complete?
We are planning to make this conversion process as complete as it can be. This includes geometry conversion and xml conversion and potentially also more. We need to address:
 - Conversion of the wing structure geometry. Here the XML structure has changed and the interpretation of the geometry.
 - Conversion of the guide curve geometry. CPACS 3 uses a different definition of the guide curves, where we have to convert the geometry.

## How does does it work?
We are using TiXI to transform the xml. This is the easy part. The hard part is the geometry conversion. To support this process, we use both the TiGL 2 and the TiGL 3 library that are able to compute the geometries for both cpacs standards.

## Legal stuff
Copyright &copy; 2015-2016, German Aerospace Center (DLR e.V.)

This software is licensed under the Apache Public License 2.0. See `LICENSE` for details.
