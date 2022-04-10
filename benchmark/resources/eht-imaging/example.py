# https://github.com/achael/eht-imaging/blob/main/examples/example.py

# Note: this is an example sequence of commands to run in ipython
# The matplotlib windows may not open/close properly if you run this directly as a script

from __future__ import division
from __future__ import print_function

import os
import sys
import matplotlib.pyplot as plt
import numpy as np
import ehtim as eh
from   ehtim.calibrating import self_cal as sc
import time

from pathlib import Path
memoization = bool(int(os.environ.get("CHARMONIUM_CACHE_ENABLE", "0")))
print(f"{memoization=}")
if memoization:
    from charmonium.cache import memoize, FileContents, MemoizedGroup
    group = MemoizedGroup(size="10Mb")
else:
    memoize = lambda **kwargs: (lambda x: x)
    FileContents = lambda x: None
    group = None

root = Path(os.environ["eht_root"]) if "eht_root" in os.environ else Path()

#from  ehtim.plotting import self_cal as sc
plt.close('all')

ttype = 'direct'

@memoize(group=group)
def get_data():
    # Load the image and the array
    im = eh.image.load_txt(root / 'models/avery_sgra_eofn.txt')
    eht = eh.array.load_txt(root / 'arrays/EHT2017.txt')
    return im, eht

@memoize(group=group)
def get_obs(im, eht):
    # Observe the image
    # tint_sec is the integration time in seconds, and tadv_sec is the advance time between scans
    # tstart_hr is the GMST time of the start of the observation and tstop_hr is the GMST time of the end
    # bw_hz is the  bandwidth in Hz
    # sgrscat=True blurs the visibilities with the Sgr A* scattering kernel for the appropriate image frequency
    # ampcal and phasecal determine if gain variations and phase errors are included
    tint_sec = 5
    tadv_sec = 600
    tstart_hr = 0
    tstop_hr = 24
    bw_hz = 4e9
    return im.observe(eht, tint_sec, tadv_sec, tstart_hr, tstop_hr, bw_hz,
                 sgrscat=False, ampcal=True, phasecal=False)

@memoize(group=group)
def deblur(obs):
    # You can deblur the visibilities by dividing by the scattering kernel if necessary
    return obs.deblur()

def plot_stuff():
    pass
    # These are some simple plots you can check
    #obs.plotall('u','v', conj=True) # uv coverage
    #obs.plotall('uvdist','amp') # amplitude with baseline distance'
    #obs.plot_bl('SMA','ALMA','phase') # visibility phase on a baseline over time

    # You can check out the dirty image, dirty beam, and clean beam
    npix = 32
    fov = 1.5*im.xdim * im.psize # slightly enlarge the field of view
    #dim = obs.dirtyimage(npix, fov)
    #dbeam = obs.dirtybeam(npix, fov)
    #cbeam = obs.cleanbeam(npix,fov)
    #dim.display()
    #dbeam.display()
    #cbeam.display()

@memoize(group=group)
def get_params(obs):
    beamparams = obs.fit_beam() # fitted beam parameters (fwhm_maj, fwhm_min, theta) in radians
    res = obs.res() # nominal array resolution, 1/longest baseline
    return beamparams, res

@memoize(group=group)
def save_data(obs):
    # Export the visibility data to uvfits/text
    obs.save_txt('obs.txt') # exports a text file with the visibilities
    obs.save_uvfits('obs.uvp') # exports a UVFITS file modeled on template.UVP
    return FileContents("obs.txt"), FileContents("obs.uvp")

@memoize(group=group)
def get_prior(im, obs):
    # Generate an image prior
    npix = 128
    fov = 1*im.fovx()
    zbl = im.total_flux() # total flux
    prior_fwhm = 200*eh.RADPERUAS # Gaussian size in microarcssec
    emptyprior = eh.image.make_square(obs, npix, fov)
    flatprior = emptyprior.add_flat(zbl)
    gaussprior = emptyprior.add_gauss(zbl, (prior_fwhm, prior_fwhm, 0, 0, 0))
    return zbl, gaussprior

@memoize(group=group)
def fit(obs, flux, gaussprior, res):
    # Image total flux with bispectrum
    out  = eh.imager_func(obs, gaussprior, gaussprior, flux,
                          d1='bs', s1='simple',
                          alpha_s1=1, alpha_d1=100,
                          alpha_flux=100, alpha_cm=50,
                          maxit=100, ttype=ttype, show_updates=False)

    # Blur the image with a circular beam and image again to help convergance
    out = out.blur_circ(res)
    out = eh.imager_func(obs, out, out, flux,
                    d1='bs', s1='tv',
                    alpha_s1=1, alpha_d1=50,
                    alpha_flux=100, alpha_cm=50,
                    maxit=100,ttype=ttype, show_updates=False)

    out = out.blur_circ(res/2.0)
    out = eh.imager_func(obs, out, out, flux,
                    d1='bs', s1='tv',
                    alpha_s1=1, alpha_d1=10,
                    alpha_flux=100, alpha_cm=50,
                    maxit=100,ttype=ttype, show_updates=False)

    return out

def main():
    im, eht = get_data()
    obs = get_obs(im, eht)
    obs = deblur(obs)
    beamparams, res = get_params(obs)
    print("Clean beam parameters:", beamparams)
    print("Nominal Resolution:", res)
    save_data(obs)
    flux, gaussprior = get_prior(im, obs)
    out = fit(obs, flux, gaussprior, res)

if __name__ == "__main__":
    main()

## Self - calibrate and image with vis amplitudes
#obs_sc = sc.self_cal(obs, out)

#out_sc = out.blur_circ(res)
#out_sc = eh.imager_func(obs_sc, out_sc, out_sc, flux,
#                   d1='vis', s1='simple',
#                   alpha_s1=1, alpha_d1=100,
#                   alpha_flux=100, alpha_cm=50,
#                   maxit=50,ttype='nfft')


## Compare the visibility amplitudes to the data
#out = out_sc
#eh.comp_plots.plotall_obs_im_compare(obs, out,'uvdist','amp', clist=['b','m'],conj=True)

# Blur the final image with 1/2 the clean beam
# outblur = out.blur_gauss(beamparams, 0.5)
# out.display()

## Save the images
#outname = "test"
#out.save_txt(outname + '.txt')
#out.save_fits(outname + '.fits')
#outblur.save_txt(outname + '_blur.txt')
#outblur.save_fits(outname + '_blur.fits')
