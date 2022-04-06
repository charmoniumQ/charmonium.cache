# -*- coding: utf-8 -*-
"""
=====================================================================
Accessing data stored as a table in a multi-extension FITS (MEF) file
=====================================================================

FITS files can often contain large amount of multi-dimensional data and
tables. This example opens a FITS file with information
from Chandra's HETG-S instrument.

The example uses `astropy.utils.data` to download multi-extension FITS (MEF)
file, `astropy.io.fits` to investigate the header, and
`astropy.table.Table` to explore the data.


*By: Lia Corrales, Adrian Price-Whelan, and Kelle Cruz*

*License: BSD*


"""

##############################################################################
# Use `astropy.utils.data` subpackage to download the FITS file used in this
# example. Also import `~astropy.table.Table` from the `astropy.table` subpackage
# and `astropy.io.fits`

from astropy.utils.data import get_pkg_data_fileobj
from astropy.table import Table
from astropy.io import fits
import io

from pathlib import Path
import os
memoization = bool(int(os.environ.get("CHARMONIUM_CACHE_ENABLE", "0")))
print(f"{memoization=}")
if memoization:
    from charmonium.cache import memoize, FileContents, MemoizedGroup
    group = MemoizedGroup(size="1Gb")
    import charmonium.freeze
    charmonium.freeze.config.ignore_globals.add(("astropy.utils.data", "_tempfilestodel"))
else:
    memoize = lambda **kwargs: (lambda x: x)
    FileContents = lambda x: x
    group = None

if "OUTPUT_LOG" in os.environ:
    output_file = open(os.environ["OUTPUT_LOG"], "w+")
else:
    output_file = None


repeats = 2
filenames = [
    "tutorials/FITS-tables/chandra_events.fits",
    "coordinates/wright_eastmann_2014_tau_ceti.fits",
    "tutorials/FITS-images/HorseHead.fits",
]

def main():
    ##############################################################################
    # Download a FITS file

    for filename in filenames * repeats:
        print(filename, file=output_file)
        event_fileobj = io.BytesIO(get_data(filename))

        events = get_events(event_fileobj)

        print(events.columns, file=output_file)

        if "energy" in events:

            ##############################################################################
            # If a column contains unit information, it will have an associated
            # `astropy.units` object.

            print(events['energy'].unit, file=output_file)

            ##############################################################################
            # Print the data stored in the Energy column.

            print(events['energy'][:5], file=output_file)


@memoize(group=group)
def get_data(filename):
    with get_pkg_data_fileobj(filename, cache=False, encoding="binary") as fobj:
        return fobj.read()


def get_info(event_filename):
    ##############################################################################
    # Display information about the contents of the FITS file.

    return fits.info(event_filename, file=False)


def get_events(event_filename):
    ##############################################################################
    # Extension 1, EVENTS, is a Table that contains information about each X-ray
    # photon that hit Chandra's HETG-S detector.
    #
    # Use `~astropy.table.Table` to read the table
    return Table.read(event_filename, hdu=1)


if __name__ == "__main__":
    main()
