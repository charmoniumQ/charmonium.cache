import pathlib
import tarfile
from astropy.utils.data import download_file
import matplotlib.pyplot as plt
from glob import glob
import os
import numpy as np
from astropy.wcs import WCS
from astropy.io import fits
import astropy.units as u
from astropy.constants.si import c, G, M_sun, R_sun
from astropy.units import imperial
import astropy.units as u
from astropy.time import Time
from astropy.table import Column, Table
from astropy.io import ascii

from charmonium.determ_hash import determ_hash
import charmonium.freeze
from charmonium.cache import memoize, MemoizedGroup, FileContents
group = MemoizedGroup(size="1GiB")
from pathlib import Path

repeat_factor = 20

import charmonium.freeze
charmonium.freeze.config.ignore_globals.add(("astropy.utils.data", "_tempfilestodel"))
charmonium.freeze.config.ignore_globals.add(("astropy.units.core", "_unit_registries"))
charmonium.freeze.config.recursion_limit = 50

def cell1():
    working_dir_path = pathlib.Path('~/.astropy/cache/download').expanduser()
    return working_dir_path

@memoize(group=group)
def cell2(working_dir_path):
    url = 'http://data.astropy.org/tutorials/UVES/data_UVES.tar.gz'
    f = tarfile.open(download_file(url, cache=False), mode='r|*')
    f.extractall(path=working_dir_path)
    globpath = working_dir_path / 'UVES'
    filelist = list(globpath.glob('*.fits'))
    filelist.sort()
    return list(map(FileContents, filelist))

def cell3(filelist):
    sp = fits.open(filelist[0])
    sp.info()
    header = sp[0].header
    wcs = WCS(header)
    index = np.arange(header['NAXIS1'])
    wavelength = wcs.wcs_pix2world(index[:, np.newaxis], 0)
    wavelength = wavelength.flatten()
    return (header, wavelength)

def read_spec(filename):
    """Read a UVES spectrum from the ESO pipeline

    Parameters
    ----------
    filename : string
    name of the fits file with the data

    Returns
    -------
    wavelength : np.ndarray
    wavelength (in Ang)
    flux : np.ndarray
    flux (in erg/s/cm**2)
    date_obs : string
    time of observation
    """
    sp = fits.open(filename)
    header = sp[0].header
    wcs = WCS(header)
    index = np.arange(header['NAXIS1'])
    wavelength = wcs.wcs_pix2world(index[:, np.newaxis], 0)
    wavelength = wavelength.flatten()
    flux = sp[0].data
    date_obs = header['Date-OBS']
    return (wavelength, flux, date_obs)

def read_setup(filename):
    """Get setup for UVES spectrum from the ESO pipeline

    Parameters
    ----------
    filename : string
    name of the fits file with the data

    Returns
    -------
    exposure_time : float
    wavelength_zero_point : float
    optical_arm : string
    """
    sp = fits.open(filename)
    header = sp[0].header
    return (header['EXPTIME'], header['CRVAL1'], header['HIERARCH ESO INS PATH'])

@memoize(group=group)
def cell8(filelist):
    for _ in range(repeat_factor):
        setups = []
        for f in filelist:
            setups.append(read_setup(f))
    return setups

@memoize(group=group)
def cell9(len_wavelength, filelist):
    for _ in range(repeat_factor):
        flux = np.zeros((len(filelist), len_wavelength))
        date = np.zeros(len(filelist), dtype='U23')
        for (i, fname) in enumerate(filelist):
            (w, f, date_obs) = read_spec(fname)
            flux[i, :] = f
            date[i] = date_obs
    return (date, flux)

@memoize(group=group)
def cell10(wavelength):
    wavelength = wavelength * u.AA
    heliocentric = -23.0 * u.km / u.s
    v_rad = -4.77 * u.km / u.s
    R_MN_Lup = 0.9 * R_sun
    M_MN_Lup = 0.6 * M_sun
    vsini = 74.6 * u.km / u.s
    period = 0.439 * u.day
    inclination = 45.0 * u.degree
    incl = inclination.to(u.radian)
    return (heliocentric, wavelength, vsini, R_MN_Lup, period, M_MN_Lup, incl)

def cell11(M_MN_Lup, R_MN_Lup):
    v_accr = (2.0 * G * M_MN_Lup / R_MN_Lup) ** 0.5
    return v_accr

def cell12(incl, vsini, v_accr):
    v_rot = vsini / np.sin(incl)
    v_accr / v_rot
    return v_rot

@memoize(group=group)
def cell13(v_accr, v_rot):
    return (v_accr / v_rot).decompose()

@memoize(group=group)
def cell14(heliocentric, wavelength):
    wavelength = wavelength * (1.0 + heliocentric / c)
    return wavelength

@memoize(group=group)
def cell15(heliocentric, wavelength):
    wavelength = wavelength * (1.0 * u.dimensionless_unscaled + heliocentric / c)
    return wavelength

@memoize(group=group)
def cell16(wavelength):
    return (
        wavelength.to(u.keV, equivalencies=u.spectral()),
        wavelength.to(u.Hz, equivalencies=u.spectral()),
    )

def cell17(M_MN_Lup, R_MN_Lup):
    return np.log10(G * M_MN_Lup / R_MN_Lup ** 2 / u.cm * u.second ** 2)

def cell18():
    waveclosetoHa = np.array([6562.0, 6563, 6565.0]) * u.AA
    return waveclosetoHa

@memoize(group=group)
def wave2doppler(w, w0):
    w0_equiv = u.doppler_optical(w0)
    w_equiv = w.to(u.km / u.s, equivalencies=w0_equiv)
    return w_equiv

@memoize(group=group)
def cell19(waveclosetoHa):
    return wave2doppler(waveclosetoHa, 656.489 * u.nm).to(u.km / u.s)

def w2vsini(w, w0, vsini):
    v = wave2doppler(w, w0) - 4.77 * u.km/u.s
    return v / vsini

def cell22(header):
    t1 = Time(header['MJD-Obs'], format='mjd', scale='utc')
    t2 = Time(header['Date-Obs'], scale='utc')
    return (t2, t1)

@memoize(group=group)
def cell25(date):
    obs_times = Time(date, scale='utc')
    delta_t = obs_times - Time(date[0], scale='utc')
    return delta_t

@memoize(group=group)
def cell26(period, delta_t):
    delta_p = delta_t.value * u.day / period
    return delta_p

@memoize(group=group)
def region_around_line(w, flux, cont):
    """cut out and normalize flux around a line

    Parameters
    ----------
    w : 1 dim np.ndarray
    array of wavelengths
    flux : np.ndarray of shape (N, len(w))
    array of flux values for different spectra in the series
    cont : list of lists
    wavelengths for continuum normalization [[low1,up1],[low2, up2]]
    that described two areas on both sides of the line
    """
    indcont = (w > cont[0][0]) & (w < cont[0][1]) | (w > cont[1][0]) & (w < cont[1][1])
    indrange = (w > cont[0][0]) & (w < cont[1][1])
    f = np.zeros((flux.shape[0], indrange.sum()))
    for i in range(flux.shape[0]):
        linecoeff = np.polyfit(w[indcont], flux[i, indcont], 2)
        f[i, :] = flux[i, indrange] / np.polyval(linecoeff, w[indrange].value)
    return (w[indrange], f)

@memoize(group=group)
def cell27(flux, wavelength):
    (wcaII, fcaII) = region_around_line(wavelength, flux, [[3925 * u.AA, 3930 * u.AA], [3938 * u.AA, 3945 * u.AA]])
    return (fcaII, wcaII)

@memoize(group=group)
def cell28(fcaII, wcaII):
    ew = fcaII[0, :] - 1.0
    ew = ew[:-1] * np.diff(wcaII.to(u.AA).value)
    return ew.sum()

@memoize(group=group)
def cell29(fcaII, wcaII):
    delta_lam = np.diff(wcaII.to(u.AA).value)
    ew = np.sum((fcaII - 1.0)[:, :-1] * delta_lam[np.newaxis, :], axis=1)
    return ew

@memoize(group=group)
def cell30(delta_p, date, working_dir_path, ew):
    datecol = Column(name='Obs Date', data=date)
    pcol = Column(name='phase', data=delta_p, format='{:.1f}')
    ewcol = Column(name='EW', data=ew, format='{:.1f}', unit='\\AA')
    tab = Table((datecol, pcol, ewcol))
    return str(tab)

@memoize(group=group)
def cell31(wcaII, vsini):
    x = w2vsini(wcaII, 393.366 * u.nm, vsini).decompose()
    return x

def serialize_fig():
    plt.savefig("/tmp/fig.raw")
    plt.close()
    return determ_hash(Path("/tmp/fig.raw").read_bytes())

def cell32(fcaII, x):
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(x, fcaII[0, :], marker='', drawstyle='steps-mid')
    ax.set_xlim([-3, +3])
    ax.set_xlabel('line shift [v sin(i)]')
    ax.set_ylabel('flux')
    ax.set_title('Ca II H line in MN Lup')
    return serialize_fig()

def cell33(fcaII, x):
    yshift = np.arange(fcaII.shape[0]) * 0.5
    yshift[:] += 1.5
    yshift[13:] += 1
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    for i in range(25):
        ax.plot(x, fcaII[i, :] + yshift[i], 'k')
    ax.plot(x, np.mean(fcaII, axis=0))
    ax.set_xlim([-2.5, +2.5])
    ax.set_xlabel('line shift [$v \\sin i$]')
    ax.set_ylabel('flux')
    ax.set_title('Ca II H line in MN Lup')
    fig.subplots_adjust(bottom=0.15)
    return serialize_fig()

@memoize(group=group)
def cell34(fcaII):
    fmean = np.mean(fcaII, axis=0)
    fdiff = fcaII - fmean[np.newaxis, :]
    return fdiff

def cell35(fdiff):
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    im = ax.imshow(fdiff, aspect='auto', origin='lower')
    return serialize_fig()

def cell36(fdiff, delta_p, x):
    ind1 = delta_p < 1 * u.dimensionless_unscaled
    ind2 = delta_p > 1 * u.dimensionless_unscaled
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    for ind in [ind1, ind2]:
        im = ax.imshow(fdiff[ind, :], extent=(np.min(x), np.max(x), np.min(delta_p[ind]), np.max(delta_p[ind])), aspect='auto', origin='lower')
    ax.set_ylim([np.min(delta_p), np.max(delta_p)])
    ax.set_xlim([-1.9, 1.9])
    plt.draw()
    return (ind2, ind1), serialize_fig()

def cell37(x, ind1, fdiff, delta_p, ind2):
    pplot = delta_p.copy().value
    pplot[ind2] -= 1.5
    delta_t = np.median(np.diff(delta_p)) / 2.0
    delta_x = np.median(np.diff(x)) / 2.0
    fdiff = fdiff / np.max(np.abs(fdiff))
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    for ind in [ind1, ind2]:
        im = ax.imshow(fdiff[ind, :], extent=(np.min(x) - delta_x, np.max(x) + delta_x, np.min(pplot[ind]) - delta_t, np.max(pplot[ind]) + delta_t), aspect='auto', origin='lower', cmap=plt.cm.Greys_r)
    ax.set_ylim([np.min(pplot) - delta_t, np.max(pplot) + delta_t])
    ax.set_xlim([-1.9, 1.9])
    ax.set_xlabel('vel in $v\\sin i$')
    ax.xaxis.set_major_locator(plt.MaxNLocator(4))
    formatter = plt.FuncFormatter(pplot)
    # ax.yaxis.set_major_formatter(formatter)
    ax.set_ylabel('period')
    fig.subplots_adjust(left=0.15, bottom=0.15, right=0.99, top=0.99)
    return serialize_fig()

@memoize(group=group)
def make_graphs(fcaII, fdiff, delta_p, x):
    # for _ in range(repeat_factor):
    for _ in range(2):
        cell32_plot = cell32(fcaII, x)
        cell33_plot = cell33(fcaII, x)
        cell35_plot = cell35(fdiff)
        (ind2, ind1), cell36_plot = cell36(fdiff, delta_p, x)
        cell37_plot = cell37(x, ind1, fdiff, delta_p, ind2)
    return [cell33_plot, cell35_plot, cell36_plot, cell37_plot]

def main():
    working_dir_path = cell1()
    filelist = cell2(working_dir_path)
    (header, wavelength) = cell3(filelist)
    setups = cell8(filelist)
    print("setups", setups)
    (date, flux) = cell9(len(wavelength), filelist)
    print("date", date)
    print("flux", flux)
    (heliocentric, wavelength, vsini, R_MN_Lup, period, M_MN_Lup, incl) = cell10(wavelength)
    print(heliocentric, wavelength, vsini, R_MN_Lup, period, M_MN_Lup, incl)
    v_accr = cell11(M_MN_Lup, R_MN_Lup)
    print("v_accr", v_accr, "v_accr.cgs", v_accr.cgs)
    print("v_accr.to", v_accr.to(imperial.yd / u.hour))
    v_rot = cell12(incl, vsini, v_accr)
    print("v_rot", v_rot)
    decomposed = cell13(v_accr, v_rot)
    print("decomposed", decomposed)
    wavelength = cell14(heliocentric, wavelength)
    print("wavelength", wavelength)
    wavelength = cell15(heliocentric, wavelength)
    print("wavelength", wavelength)
    converted_wavelengths = cell16(wavelength)
    print("converted_wavelengths", converted_wavelengths)
    print("cell17", cell17(M_MN_Lup, R_MN_Lup))
    waveclosetoHa = cell18()
    print("waveclosetoHa", waveclosetoHa)
    wave2doppler_result = cell19(waveclosetoHa)
    print("wave2doppler_result", wave2doppler_result)
    (t2, t1) = cell22(header)
    print("t1, t2", t1, t2)
    delta_t = cell25(date)
    delta_p = cell26(period, delta_t)
    print("delta_t", "delta_p", delta_t, delta_p)
    (fcaII, wcaII) = cell27(flux, wavelength)
    print("fcaII", fcaII, "wcaII", wcaII[-5:])
    sum = cell28(fcaII, wcaII)
    print("sum", sum)
    ew = cell29(fcaII, wcaII)
    print("ew", ew)
    table = cell30(delta_p, date, working_dir_path, ew)
    print("table", table)
    x = cell31(wcaII, vsini)
    print("x", x[-5:])
    fdiff = cell34(fcaII)
    print("fidff", fdiff)
    graphs = make_graphs(fcaII, fdiff, delta_p, x)
    for i, graph in enumerate(graphs):
        print("graphs", i, graph)

if __name__ == '__main__':
    main()
