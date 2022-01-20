import exoplanet
import sys
import base64
import matplotlib.pyplot as plt
import arviz as az
import functools
import pymc3 as pm
import numpy as np
import os
import io
from pathlib import Path
import tempfile
import logging
import charmonium.cache

@charmonium.cache.memoize()
def get_data():
    import requests
    # Download the dataset from the Exoplanet Archive:
    url = "https://exoplanetarchive.ipac.caltech.edu/data/ExoData/0113/0113357/data/UID_0113357_RVC_001.tbl"
    r = requests.get(url)
    if r.status_code != requests.codes.ok:
        r.raise_for_status()
    return r.text

@charmonium.cache.memoize()
def parse_data(r_text):
    data = np.array(
        [
            l.split()
            for l in r_text.splitlines()
            if not l.startswith("\\") and not l.startswith("|")
        ],
        dtype=float,
    )
    t, rv, rv_err = data.T
    t -= np.mean(t)
    phase = np.linspace(0, 1, 500)
    return t, rv, rv_err, phase

@charmonium.cache.memoize()
def plot_data(t, rv, rv_err):
    # Plot the observations "folded" on the published period:
    # Butler et al. (2006) https://arxiv.org/abs/astro-ph/0607493
    lit_period = 4.230785
    plt.errorbar(
        (t % lit_period) / lit_period, rv, yerr=rv_err, fmt=".k", capsize=0
    )
    plt.xlim(0, 1)
    plt.ylim(-110, 110)
    plt.annotate(
        "period = {0:.6f} days".format(lit_period),
        xy=(1, 0),
        xycoords="axes fraction",
        xytext=(-5, 5),
        textcoords="offset points",
        ha="right",
        va="bottom",
        fontsize=12,
    )
    plt.ylabel("radial velocity [m/s]")
    plt.xlabel("phase")
    return plt.gcf(), lit_period

def get_model(t, rv, rv_err, lit_period, phase):
    import pymc3_ext as pmx
    import aesara_theano_fallback.tensor as tt
    import exoplanet as xo

    with pm.Model() as model:

        # Parameters
        logK = pm.Uniform(
            "logK",
            lower=0,
            upper=np.log(200),
            testval=np.log(0.5 * (np.max(rv) - np.min(rv))),
        )
        logP = pm.Uniform(
            "logP", lower=0, upper=np.log(10), testval=np.log(lit_period)
        )
        phi = pm.Uniform("phi", lower=0, upper=2 * np.pi, testval=0.1)

        # Parameterize the eccentricity using:
        #  h = sqrt(e) * sin(w)
        #  k = sqrt(e) * cos(w)
        hk = pmx.UnitDisk("hk", testval=np.array([0.01, 0.01]))
        e = pm.Deterministic("e", hk[0] ** 2 + hk[1] ** 2)
        w = pm.Deterministic("w", tt.arctan2(hk[1], hk[0]))

        rv0 = pm.Normal("rv0", mu=0.0, sd=10.0, testval=0.0)
        rvtrend = pm.Normal("rvtrend", mu=0.0, sd=10.0, testval=0.0)

        # Deterministic transformations
        n = 2 * np.pi * tt.exp(-logP)
        P = pm.Deterministic("P", tt.exp(logP))
        K = pm.Deterministic("K", tt.exp(logK))
        cosw = tt.cos(w)
        sinw = tt.sin(w)
        t0 = (phi + w) / n

        # The RV model
        bkg = pm.Deterministic("bkg", rv0 + rvtrend * t / 365.25)
        M = n * t - (phi + w)

        # This is the line that uses the custom Kepler solver
        f = xo.orbits.get_true_anomaly(M, e + tt.zeros_like(M))
        rvmodel = pm.Deterministic(
            "rvmodel", bkg + K * (cosw * (tt.cos(f) + e) - sinw * tt.sin(f))
        )

        # Condition on the observations
        pm.Normal("obs", mu=rvmodel, sd=rv_err, observed=rv)

        # Compute the phased RV signal
        M_pred = 2 * np.pi * phase - (phi + w)
        f_pred = xo.orbits.get_true_anomaly(M_pred, e + tt.zeros_like(M_pred))
        rvphase = pm.Deterministic(
            "rvphase", K * (cosw * (tt.cos(f_pred) + e) - sinw * tt.sin(f_pred))
        )
        return model

@charmonium.cache.memoize()
def get_map_params(model_fn):
    import pymc3_ext as pmx
    with model_fn():
        map_params = pmx.optimize()
    return map_params

@charmonium.cache.memoize()
def plot_params(t, rv, rv_err, phase, map_params):
    fig, axes = plt.subplots(2, 1, figsize=(8, 8))

    period = map_params["P"]

    ax = axes[0]
    ax.errorbar(t, rv, yerr=rv_err, fmt=".k")
    ax.plot(t, map_params["bkg"], color="C0", lw=1)
    ax.set_ylim(-110, 110)
    ax.set_ylabel("radial velocity [m/s]")
    ax.set_xlabel("time [days]")

    ax = axes[1]
    ax.errorbar(t % period, rv - map_params["bkg"], yerr=rv_err, fmt=".k")
    ax.plot(phase * period, map_params["rvphase"], color="C1", lw=1)
    ax.set_ylim(-110, 110)
    ax.set_ylabel("radial velocity [m/s]")
    ax.set_xlabel("phase [days]")

    plt.tight_layout()
    return fig

@charmonium.cache.memoize()
def run_model(model_fn, map_params):
    import pymc3_ext as pmx
    with model_fn():
        trace = pmx.sample(
            draws=300,
            tune=300,
            start=map_params,
            chains=2,
            cores=2,
            target_accept=0.95,
            return_inferencedata=True,
        )
    return trace

@charmonium.cache.memoize()
def summarize_model(trace):
    az.summary(
        trace,
        var_names=["logK", "logP", "phi", "e", "w", "rv0", "rvtrend"],
    )
    import corner
    corner.corner(trace, var_names=["K", "P", "e", "w"])
    return plt.gcf()

@charmonium.cache.memoize()
def plot_sample(t, rv, rv_err, phase, map_params, trace):
    fig, axes = plt.subplots(2, 1, figsize=(8, 8))

    period = map_params["P"]

    ax = axes[0]
    ax.errorbar(t, rv, yerr=rv_err, fmt=".k")
    ax.set_ylabel("radial velocity [m/s]")
    ax.set_xlabel("time [days]")

    ax = axes[1]
    ax.errorbar(t % period, rv - map_params["bkg"], yerr=rv_err, fmt=".k")
    ax.set_ylabel("radial velocity [m/s]")
    ax.set_xlabel("phase [days]")

    bkg = trace.posterior["bkg"].values
    rvphase = trace.posterior["rvphase"].values

    for ind in np.random.randint(np.prod(bkg.shape[:2]), size=25):
        i = np.unravel_index(ind, bkg.shape[:2])
        axes[0].plot(t, bkg[i], color="C0", lw=1, alpha=0.3)
        axes[1].plot(phase * period, rvphase[i], color="C1", lw=1, alpha=0.3)

    axes[0].set_ylim(-110, 110)
    axes[1].set_ylim(-110, 110)

    plt.tight_layout()

    return plt.gcf()


def main2():
    output = io.BytesIO()
    r_text = get_data()
    t, rv, rv_err, phase = parse_data(r_text)
    fig, lit_data = plot_data(t, rv, rv_err)
    fig.savefig(output, format="png")
    model_fn = functools.partial(get_model, t, rv, rv_err, lit_data, phase)
    map_params = get_map_params(model_fn)
    plot_params(t, rv, rv_err, phase, map_params).savefig(output, format="png")
    trace = run_model(model_fn, map_params)
    summarize_model(trace).savefig(output, format="png")
    plot_sample(t, rv, rv_err, phase, map_params, trace).savefig(output, format="png")
    # sys.stdout.buffer.write(base64.b64encode(output.getvalue()))

main2()
