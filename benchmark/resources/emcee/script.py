import matplotlib.pyplot as plt
import time
import h5py
from multiprocessing import cpu_count
import emcee
import celerite
from matplotlib import rcParams
import os
import numpy as np
import corner
from multiprocessing import Pool
from celerite import terms
from IPython.display import display, Math
from scipy.optimize import minimize
import multiprocessing


from charmonium.freeze import freeze, config as freeze_config
from charmonium.determ_hash import determ_hash
from charmonium.cache import memoize, MemoizedGroup, FileContents
from pathlib import Path

freeze_config.recursion_limit = 150
freeze_config.constant_functions.add(("charmonium.freeze.lib", "freeze"))
freeze_config.constant_functions.add(("charmonium.determ_hash.lib", "determ_hash"))
freeze_config.constant_classes  .add(("charmonium.cache.memoize", "Memoized"))
freeze_config.constant_classes  .add(("charmonium.cache.memoize", "MemoizedGroup"))
freeze_config.constant_objects.add(('numpy', 'ufunc'))
freeze_config.constant_objects.add(('builtins', 'fortran'))

# import logging, os
# logger = logging.getLogger("charmonium.freeze")
# logger.setLevel(logging.DEBUG)
# fh = logging.FileHandler("freeze.log")
# fh.setLevel(logging.DEBUG)
# fh.setFormatter(logging.Formatter("%(message)s"))
# logger.addHandler(fh)
# logger.debug("Program %d", os.getpid())

group = MemoizedGroup(size="1GiB")

def print_plt(old_func):
    def new_func(*args, **kwargs):
        ret = old_func(*args, **kwargs)
        plt.savefig("/tmp/fig.raw")
        plt.close()
        plot = Path("/tmp/fig.raw").read_bytes()
        undecorated_old_func = getattr(old_func, "_func", old_func)
        print(undecorated_old_func.__name__, "plt", determ_hash(plot))
        return ret
    return new_func

def print_ret(old_func):
    def new_func(*args, **kwargs):
        ret = old_func(*args, **kwargs)
        undecorated_old_func = getattr(old_func, "_func", old_func)
        print(undecorated_old_func.__name__, determ_hash(freeze(ret)))
        return ret
    return new_func


@memoize(group=group)
def cell0_autocorr():
    """ %config InlineBackend.figure_format = "retina" """
    rcParams['savefig.dpi'] = 100
    rcParams['figure.dpi'] = 100
    rcParams['font.size'] = 20

@print_ret
@print_plt
@memoize(group=group)
def cell1_autocorr():
    np.random.seed(1234)
    kernel = terms.RealTerm(log_a=0.0, log_c=-6.0)
    kernel += terms.RealTerm(log_a=0.0, log_c=-2.0)
    true_tau = sum((2 * np.exp(t.log_a - t.log_c) for t in kernel.terms))
    true_tau /= sum((np.exp(t.log_a) for t in kernel.terms))
    gp = celerite.GP(kernel)
    t = np.arange(2000000)
    gp.compute(t)
    y = gp.sample(size=32)
    plt.plot(y[:3, :300].T)
    plt.xlim(0, 300)
    plt.xlabel('step number')
    plt.ylabel('$f$')
    cell1_output = plt.title('$\\tau_\\mathrm{{true}} = {0:.0f}$'.format(true_tau), fontsize=14)
    if cell1_output is not None:
        print('cell1_output', cell1_output)
    return y, true_tau, kernel

@print_ret
@memoize(group=group)
def next_pow_two(n):
    i = 1
    while i < n:
        i = i << 1
    return i

@print_ret
@memoize(group=group)
def autocorr_func_1d(x, norm=True):
    x = np.atleast_1d(x)
    if len(x.shape) != 1:
        raise ValueError('invalid dimensions for 1D autocorrelation function')
    n = next_pow_two(len(x))
    f = np.fft.fft(x - np.mean(x), n=2 * n)
    acf = np.fft.ifft(f * np.conjugate(f))[:len(x)].real
    acf /= 4 * n
    if norm:
        acf /= acf[0]
    return acf

@print_ret
@print_plt
@memoize(group=group)
def cell2_autocorr(y, true_tau, kernel):
    window = int(2 * true_tau)
    tau = np.arange(window + 1)
    f0 = kernel.get_value(tau) / kernel.get_value(0.0)
    (fig, axes) = plt.subplots(1, 3, figsize=(12, 4), sharex=True, sharey=True)
    for (n, ax) in zip([10, 100, 1000], axes):
        nn = int(true_tau * n)
        ax.plot(tau / true_tau, f0, 'k', label='true')
        ax.plot(tau / true_tau, autocorr_func_1d(y[0, :nn])[:window + 1], label='estimate')
        ax.set_title('$N = {0}\\,\\tau_\\mathrm{{true}}$'.format(n), fontsize=14)
        ax.set_xlabel('$\\tau / \\tau_\\mathrm{true}$')
    axes[0].set_ylabel('$\\rho_f(\\tau)$')
    axes[-1].set_xlim(0, window / true_tau)
    axes[-1].set_ylim(-0.05, 1.05)
    cell2_output = axes[-1].legend(fontsize=14)
    if cell2_output is not None:
        print('cell2_output', cell2_output)
    return (tau, window, autocorr_func_1d, f0)

@print_plt
@memoize(group=group)
def cell3_autocorr(tau, window, autocorr_func_1d, f0, y):
    (fig, axes) = plt.subplots(1, 3, figsize=(12, 4), sharex=True, sharey=True)
    for (n, ax) in zip([10, 100, 1000], axes):
        nn = int(true_tau * n)
        ax.plot(tau / true_tau, f0, 'k', label='true')
        f = np.mean([autocorr_func_1d(y[i, :nn], norm=False)[:window + 1] for i in range(len(y))], axis=0)
        f /= f[0]
        ax.plot(tau / true_tau, f, label='estimate')
        ax.set_title('$N = {0}\\,\\tau_\\mathrm{{true}}$'.format(n), fontsize=14)
        ax.set_xlabel('$\\tau / \\tau_\\mathrm{true}$')
    axes[0].set_ylabel('$\\rho_f(\\tau)$')
    axes[-1].set_xlim(0, window / true_tau)
    axes[-1].set_ylim(-0.05, 1.05)
    cell3_output = axes[-1].legend(fontsize=14)
    if cell3_output is not None:
        print('cell3_output', cell3_output)

@print_ret
@memoize(group=group)
def auto_window(taus, c):
    m = np.arange(len(taus)) < c * taus
    if np.any(m):
        return np.argmin(m)
    return len(taus) - 1

@print_ret
@memoize(group=group)
def autocorr_gw2010(y, c=5.0):
    f = autocorr_func_1d(np.mean(y, axis=0))
    taus = 2.0 * np.cumsum(f) - 1.0
    window = auto_window(taus, c)
    return taus[window]

@print_ret
@memoize(group=group)
def autocorr_new(y, c=5.0):
    f = np.zeros(y.shape[1])
    for yy in y:
        f += autocorr_func_1d(yy)
    f /= len(y)
    taus = 2.0 * np.cumsum(f) - 1.0
    window = auto_window(taus, c)
    return taus[window]

@print_ret
@print_plt
@memoize(group=group)
def cell4_autocorr(y, autocorr_func_1d):
    N = np.exp(np.linspace(np.log(100), np.log(y.shape[1]), 10)).astype(int)
    gw2010 = np.empty(len(N))
    new = np.empty(len(N))
    for (i, n) in enumerate(N):
        gw2010[i] = autocorr_gw2010(y[:, :n])
        new[i] = autocorr_new(y[:, :n])
    plt.loglog(N, gw2010, 'o-', label='G&W 2010')
    plt.loglog(N, new, 'o-', label='new')
    ylim = plt.gca().get_ylim()
    plt.plot(N, N / 50.0, '--k', label='$\\tau = N/50$')
    plt.axhline(true_tau, color='k', label='truth', zorder=-100)
    plt.ylim(ylim)
    plt.xlabel('number of samples, $N$')
    plt.ylabel('$\\tau$ estimates')
    cell4_output = plt.legend(fontsize=14)
    if cell4_output is not None:
        print('cell4_output', cell4_output)
    return (autocorr_new, autocorr_gw2010)

@print_ret
@memoize(group=group)
def log_prob(p):
    return np.logaddexp(-0.5 * np.sum(p ** 2), -0.5 * np.sum((p - 4.0) ** 2))

@print_ret
@memoize(group=group)
def cell5_autocorr():
    sampler = emcee.EnsembleSampler(32, 3, log_prob)
    cell5_output = sampler.run_mcmc(np.concatenate((np.random.randn(16, 3), 4.0 + np.random.randn(16, 3)), axis=0), 500000, progress=True)
    if cell5_output is not None:
        print('cell5_output', cell5_output)
    return sampler

@print_ret
@print_plt
@memoize(group=group)
def cell6_autocorr(sampler):
    chain = sampler.get_chain()[:, :, 0].T
    plt.hist(chain.flatten(), 100)
    plt.gca().set_yticks([])
    plt.xlabel('$\\theta$')
    cell6_output = plt.ylabel('$p(\\theta)$')
    if cell6_output is not None:
        print('cell6_output', cell6_output)
    return chain

@print_ret
@print_plt
@memoize(group=group)
def cell7_autocorr(autocorr_new, autocorr_gw2010, chain):
    N = np.exp(np.linspace(np.log(100), np.log(chain.shape[1]), 10)).astype(int)
    gw2010 = np.empty(len(N))
    new = np.empty(len(N))
    for (i, n) in enumerate(N):
        gw2010[i] = autocorr_gw2010(chain[:, :n])
        new[i] = autocorr_new(chain[:, :n])
    plt.loglog(N, gw2010, 'o-', label='G&W 2010')
    plt.loglog(N, new, 'o-', label='new')
    ylim = plt.gca().get_ylim()
    plt.plot(N, N / 50.0, '--k', label='$\\tau = N/50$')
    plt.ylim(ylim)
    plt.xlabel('number of samples, $N$')
    plt.ylabel('$\\tau$ estimates')
    cell7_output = plt.legend(fontsize=14)
    if cell7_output is not None:
        print('cell7_output', cell7_output)
    return (N, new, gw2010)

@print_ret
@memoize(group=group)
def autocorr_ml(y, kernel, thin=1, c=5.0):
    init = autocorr_new(y, c=c)
    z = y[:, ::thin]
    N = z.shape[1]
    tau = max(1.0, init / thin)
    kernel = terms.RealTerm(np.log(0.9 * np.var(z)), -np.log(tau), bounds=[(-5.0, 5.0), (-np.log(N), 0.0)])
    kernel += terms.RealTerm(np.log(0.1 * np.var(z)), -np.log(0.5 * tau), bounds=[(-5.0, 5.0), (-np.log(N), 0.0)])
    gp = celerite.GP(kernel, mean=np.mean(z))
    gp.compute(np.arange(z.shape[1]))

    def nll(p):
        gp.set_parameter_vector(p)
        (v, g) = zip(*(gp.grad_log_likelihood(z0, quiet=True) for z0 in z))
        return (-np.sum(v), -np.sum(g, axis=0))
    p0 = gp.get_parameter_vector()
    bounds = gp.get_parameter_bounds()
    soln = minimize(nll, p0, jac=True, bounds=bounds)
    gp.set_parameter_vector(soln.x)
    (a, c) = kernel.coefficients[:2]
    tau = thin * 2 * np.sum(a / c) / np.sum(a)
    return tau

@print_ret
@memoize(group=group)
def cell8_autocorr(autocorr_new, N, chain, new, kernel):
    ml = np.empty(len(N))
    ml[:] = np.nan
    for (j, n) in enumerate(N[1:8]):
        i = j + 1
        thin = max(1, int(0.05 * new[i]))
        ml[i] = autocorr_ml(chain[:, :n], kernel, thin=thin)
    return ml

@print_plt
@memoize(group=group)
def cell9_autocorr(N, ml, new, gw2010):
    plt.loglog(N, gw2010, 'o-', label='G&W 2010')
    plt.loglog(N, new, 'o-', label='new')
    plt.loglog(N, ml, 'o-', label='ML')
    ylim = plt.gca().get_ylim()
    plt.plot(N, N / 50.0, '--k', label='$\\tau = N/50$')
    plt.ylim(ylim)
    plt.xlabel('number of samples, $N$')
    plt.ylabel('$\\tau$ estimates')
    cell9_output = plt.legend(fontsize=14)
    if cell9_output is not None:
        print('cell9_output', cell9_output)

@memoize(group=group)
def main_autocorr():
    cell0_autocorr()
    y, true_tau, kernel = cell1_autocorr()
    (tau, window, autocorr_func_1d, f0) = cell2_autocorr(y, true_tau, kernel)
    cell3_autocorr(tau, window, autocorr_func_1d, f0, y)
    (autocorr_new, autocorr_gw2010) = cell4_autocorr(y, autocorr_func_1d)
    sampler = cell5_autocorr()
    chain = cell6_autocorr(sampler)
    (N, new, gw2010) = cell7_autocorr(autocorr_new, autocorr_gw2010, chain)
    ml = cell8_autocorr(autocorr_new, N, chain, new, kernel)
    cell9_autocorr(N, ml, new, gw2010)

@memoize(group=group)
def cell0_line():
    """ %config InlineBackend.figure_format = "retina" """
    rcParams['savefig.dpi'] = 100
    rcParams['figure.dpi'] = 100
    rcParams['font.size'] = 20

@print_ret
@print_plt
@memoize(group=group)
def cell1_line():
    np.random.seed(123)
    m_true = -0.9594
    b_true = 4.294
    f_true = 0.534
    N = 50
    x = np.sort(10 * np.random.rand(N))
    yerr = 0.1 + 0.5 * np.random.rand(N)
    y = m_true * x + b_true
    y += np.abs(f_true * y) * np.random.randn(N)
    y += yerr * np.random.randn(N)
    plt.errorbar(x, y, yerr=yerr, fmt='.k', capsize=0)
    x0 = np.linspace(0, 10, 500)
    plt.plot(x0, m_true * x0 + b_true, 'k', alpha=0.3, lw=3)
    plt.xlim(0, 10)
    plt.xlabel('x')
    cell1_output = plt.ylabel('y')
    if cell1_output is not None:
        print('cell1_output', cell1_output)
    return (f_true, x, x0, yerr, m_true, b_true)

@print_ret
@print_plt
@memoize(group=group)
def cell2_line(x, x0, yerr, m_true, b_true):
    A = np.vander(x, 2)
    C = np.diag(yerr * yerr)
    ATA = np.dot(A.T, A / (yerr ** 2)[:, None])
    cov = np.linalg.inv(ATA)
    w = np.linalg.solve(ATA, np.dot(A.T, y / yerr ** 2))
    print('Least-squares estimates:')
    print('m = {0:.3f} ± {1:.3f}'.format(w[0], np.sqrt(cov[0, 0])))
    print('b = {0:.3f} ± {1:.3f}'.format(w[1], np.sqrt(cov[1, 1])))
    plt.errorbar(x, y, yerr=yerr, fmt='.k', capsize=0)
    plt.plot(x0, m_true * x0 + b_true, 'k', alpha=0.3, lw=3, label='truth')
    plt.plot(x0, np.dot(np.vander(x0, 2), w), '--k', label='LS')
    plt.legend(fontsize=14)
    plt.xlim(0, 10)
    plt.xlabel('x')
    cell2_output = plt.ylabel('y')
    if cell2_output is not None:
        print('cell2_output', cell2_output)
    return w

@print_ret
@memoize(group=group)
def log_likelihood(theta, x, y, yerr):
    (m, b, log_f) = theta
    model = m * x + b
    sigma2 = yerr ** 2 + model ** 2 * np.exp(2 * log_f)
    return -0.5 * np.sum((y - model) ** 2 / sigma2 + np.log(sigma2))

@print_ret
@print_plt
@memoize(group=group)
def cell4_line(f_true, x, x0, yerr, m_true, log_likelihood, b_true, w):
    np.random.seed(42)
    nll = lambda *args: -log_likelihood(*args)
    initial = np.array([m_true, b_true, np.log(f_true)]) + 0.1 * np.random.randn(3)
    soln = minimize(nll, initial, args=(x, y, yerr))
    (m_ml, b_ml, log_f_ml) = soln.x
    print('Maximum likelihood estimates:')
    print('m = {0:.3f}'.format(m_ml))
    print('b = {0:.3f}'.format(b_ml))
    print('f = {0:.3f}'.format(np.exp(log_f_ml)))
    plt.errorbar(x, y, yerr=yerr, fmt='.k', capsize=0)
    plt.plot(x0, m_true * x0 + b_true, 'k', alpha=0.3, lw=3, label='truth')
    plt.plot(x0, np.dot(np.vander(x0, 2), w), '--k', label='LS')
    plt.plot(x0, np.dot(np.vander(x0, 2), [m_ml, b_ml]), ':k', label='ML')
    plt.legend(fontsize=14)
    plt.xlim(0, 10)
    plt.xlabel('x')
    cell4_output = plt.ylabel('y')
    if cell4_output is not None:
        print('cell4_output', cell4_output)
    return soln

@print_ret
@memoize(group=group)
def log_prior(theta):
    (m, b, log_f) = theta
    if -5.0 < m < 0.5 and 0.0 < b < 10.0 and (-10.0 < log_f < 1.0):
        return 0.0
    return -np.inf

@print_ret
@memoize(group=group)
def log_probability(theta, x, y, yerr):
    lp = log_prior(theta)
    if not np.isfinite(lp):
        return -np.inf
    return lp + log_likelihood(theta, x, y, yerr)

@print_ret
@memoize(group=group)
def cell7_line(soln, yerr, x, log_probability):
    pos = soln.x + 0.0001 * np.random.randn(32, 3)
    (nwalkers, ndim) = pos.shape
    sampler = emcee.EnsembleSampler(nwalkers, ndim, log_probability, args=(x, y, yerr))
    cell7_output = sampler.run_mcmc(pos, 5000, progress=True)
    if cell7_output is not None:
        print('cell7_output', cell7_output)
    return (ndim, sampler)

@print_ret
@print_plt
@memoize(group=group)
def cell8_line(ndim, sampler):
    (fig, axes) = plt.subplots(3, figsize=(10, 7), sharex=True)
    samples = sampler.get_chain()
    labels = ['m', 'b', 'log(f)']
    for i in range(ndim):
        ax = axes[i]
        ax.plot(samples[:, :, i], 'k', alpha=0.3)
        ax.set_xlim(0, len(samples))
        ax.set_ylabel(labels[i])
        ax.yaxis.set_label_coords(-0.1, 0.5)
    cell8_output = axes[-1].set_xlabel('step number')
    if cell8_output is not None:
        print('cell8_output', cell8_output)
    return labels

@memoize(group=group)
def cell9_line(sampler):
    tau = sampler.get_autocorr_time()
    cell9_output = print(tau)
    if cell9_output is not None:
        print('cell9_output', cell9_output)

@print_ret
@memoize(group=group)
def cell10_line(sampler):
    flat_samples = sampler.get_chain(discard=100, thin=15, flat=True)
    cell10_output = print(flat_samples.shape)
    if cell10_output is not None:
        print('cell10_output', cell10_output)
    return flat_samples

@memoize(group=group)
def cell11_line(f_true, labels, flat_samples, m_true, b_true):
    fig = corner.corner(flat_samples, labels=labels, truths=[m_true, b_true, np.log(f_true)])

@print_plt
@memoize(group=group)
def cell12_line(x, x0, flat_samples, yerr, m_true, b_true):
    inds = np.random.randint(len(flat_samples), size=100)
    for ind in inds:
        sample = flat_samples[ind]
        plt.plot(x0, np.dot(np.vander(x0, 2), sample[:2]), 'C1', alpha=0.1)
    plt.errorbar(x, y, yerr=yerr, fmt='.k', capsize=0)
    plt.plot(x0, m_true * x0 + b_true, 'k', label='truth')
    plt.legend(fontsize=14)
    plt.xlim(0, 10)
    plt.xlabel('x')
    cell12_output = plt.ylabel('y')
    if cell12_output is not None:
        print('cell12_output', cell12_output)

@memoize(group=group)
def cell13_line(ndim, flat_samples, labels):
    for i in range(ndim):
        mcmc = np.percentile(flat_samples[:, i], [16, 50, 84])
        q = np.diff(mcmc)
        txt = '\\mathrm{{{3}}} = {0:.3f}_{{-{1:.3f}}}^{{{2:.3f}}}'
        txt = txt.format(mcmc[1], q[0], q[1], labels[i])
        display(Math(txt))

@memoize(group=group)
def main_line():
    cell0_line()
    (f_true, x, x0, yerr, m_true, b_true) = cell1_line()
    w = cell2_line(x, x0, yerr, m_true, b_true)
    soln = cell4_line(f_true, x, x0, yerr, m_true, log_likelihood, b_true, w)
    (ndim, sampler) = cell7_line(soln, yerr, x, log_probability)
    labels = cell8_line(ndim, sampler)
    cell9_line(sampler)
    flat_samples = cell10_line(sampler)
    cell11_line(f_true, labels, flat_samples, m_true, b_true)
    cell12_line(x, x0, flat_samples, yerr, m_true, b_true)
    cell13_line(ndim, flat_samples, labels)

@memoize(group=group)
def cell0_monitor():
    """ %config InlineBackend.figure_format = "retina" """
    rcParams['savefig.dpi'] = 100
    rcParams['figure.dpi'] = 100
    rcParams['font.size'] = 20

@print_ret
@memoize(group=group)
def log_prob(theta):
    log_prior = -0.5 * np.sum((theta - 1.0) ** 2 / 100.0)
    log_prob = -0.5 * np.sum(theta ** 2) + log_prior
    return (log_prob, log_prior)

@print_ret
@memoize(group=group)
def cell1_monitor():
    np.random.seed(42)
    coords = np.random.randn(32, 5)
    (nwalkers, ndim) = coords.shape
    filename = 'tutorial.h5'
    backend = emcee.backends.HDFBackend(filename)
    backend.reset(nwalkers, ndim)
    sampler = emcee.EnsembleSampler(nwalkers, ndim, log_prob, backend=backend)
    return (log_prob, filename, nwalkers, coords, sampler, ndim)

@print_ret
@memoize(group=group)
def cell2_monitor(coords, sampler):
    max_n = 100000
    index = 0
    autocorr = np.empty(max_n)
    old_tau = np.inf
    for sample in sampler.sample(coords, iterations=max_n, progress=True):
        if sampler.iteration % 100:
            continue
        tau = sampler.get_autocorr_time(tol=0)
        autocorr[index] = np.mean(tau)
        index += 1
        converged = np.all(tau * 100 < sampler.iteration)
        converged &= np.all(np.abs(old_tau - tau) / tau < 0.01)
        if converged:
            break
        old_tau = tau
    return (index, autocorr)

@print_plt
@memoize(group=group)
def cell3_monitor(index, autocorr):
    n = 100 * np.arange(1, index + 1)
    y = autocorr[:index]
    plt.plot(n, n / 100.0, '--k')
    plt.plot(n, y)
    plt.xlim(0, n.max())
    plt.ylim(0, y.max() + 0.1 * (y.max() - y.min()))
    plt.xlabel('number of steps')
    cell3_output = plt.ylabel('mean $\\hat{\\tau}$')
    if cell3_output is not None:
        print('cell3_output', cell3_output)

@memoize(group=group)
def cell4_monitor(ndim, sampler):
    tau = sampler.get_autocorr_time()
    burnin = int(2 * np.max(tau))
    thin = int(0.5 * np.min(tau))
    samples = sampler.get_chain(discard=burnin, flat=True, thin=thin)
    log_prob_samples = sampler.get_log_prob(discard=burnin, flat=True, thin=thin)
    log_prior_samples = sampler.get_blobs(discard=burnin, flat=True, thin=thin)
    print('burn-in: {0}'.format(burnin))
    print('thin: {0}'.format(thin))
    print('flat chain shape: {0}'.format(samples.shape))
    print('flat log prob shape: {0}'.format(log_prob_samples.shape))
    print('flat log prior shape: {0}'.format(log_prior_samples.shape))
    all_samples = np.concatenate((samples, log_prob_samples[:, None], log_prior_samples[:, None]), axis=1)
    labels = list(map('$\\theta_{{{0}}}$'.format, range(1, ndim + 1)))
    labels += ['log prob', 'log prior']
    cell4_output = corner.corner(all_samples, labels=labels)
    if cell4_output is not None:
        print('cell4_output', cell4_output)

@memoize(group=group)
def cell5_monitor(filename):
    reader = emcee.backends.HDFBackend(filename)
    tau = reader.get_autocorr_time()
    burnin = int(2 * np.max(tau))
    thin = int(0.5 * np.min(tau))
    samples = reader.get_chain(discard=burnin, flat=True, thin=thin)
    log_prob_samples = reader.get_log_prob(discard=burnin, flat=True, thin=thin)
    log_prior_samples = reader.get_blobs(discard=burnin, flat=True, thin=thin)
    print('burn-in: {0}'.format(burnin))
    print('thin: {0}'.format(thin))
    print('flat chain shape: {0}'.format(samples.shape))
    print('flat log prob shape: {0}'.format(log_prob_samples.shape))
    cell5_output = print('flat log prior shape: {0}'.format(log_prior_samples.shape))
    if cell5_output is not None:
        print('cell5_output', cell5_output)

@print_ret
@memoize(group=group)
def cell6_monitor(nwalkers, log_prob, ndim, filename):
    new_backend = emcee.backends.HDFBackend(filename)
    print('Initial size: {0}'.format(new_backend.iteration))
    new_sampler = emcee.EnsembleSampler(nwalkers, ndim, log_prob, backend=new_backend)
    new_sampler.run_mcmc(None, 100)
    cell6_output = print('Final size: {0}'.format(new_backend.iteration))
    if cell6_output is not None:
        print('cell6_output', cell6_output)
    return new_backend

@print_ret
@memoize(group=group)
def log_prob2(theta):
    log_prior = -0.5 * np.sum((theta - 2.0) ** 2 / 100.0)
    log_prob = -0.5 * np.sum(theta ** 2) + log_prior
    return (log_prob, log_prior)

@memoize(group=group)
def cell7_monitor(new_backend, filename):
    run2_backend = emcee.backends.HDFBackend(filename, name='mcmc_second_prior')
    coords = np.random.randn(32, 5)
    (nwalkers, ndim) = coords.shape
    sampler2 = emcee.EnsembleSampler(nwalkers, ndim, log_prob2, backend=run2_backend)
    cell7_output = sampler2.run_mcmc(coords, new_backend.iteration, progress=True)
    if cell7_output is not None:
        print('cell7_output', cell7_output)

@memoize(group=group)
def cell8_monitor(filename):
    with h5py.File(filename, 'r') as f:
        print(list(f.keys()))

@memoize(group=group)
def main_monitor():
    cell0_monitor()
    (log_prob, filename, nwalkers, coords, sampler, ndim) = cell1_monitor()
    (index, autocorr) = cell2_monitor(coords, sampler)
    cell3_monitor(index, autocorr)
    cell4_monitor(ndim, sampler)
    cell5_monitor(filename)
    new_backend = cell6_monitor(nwalkers, log_prob, ndim, filename)
    cell7_monitor(new_backend, filename)
    cell8_monitor(filename)

@memoize(group=group)
def cell0_moves():
    """ %config InlineBackend.figure_format = "retina" """
    rcParams['savefig.dpi'] = 100
    rcParams['figure.dpi'] = 100
    rcParams['font.size'] = 20

@print_ret
@memoize(group=group)
def logprob(x):
    return np.sum(np.logaddexp(-0.5 * (x - 2) ** 2, -0.5 * (x + 2) ** 2) - 0.5 * np.log(2 * np.pi) - np.log(2))

@print_ret
@print_plt
@memoize(group=group)
def cell1_moves():
    x = np.linspace(-5.5, 5.5, 5000)
    plt.plot(x, np.exp(list(map(logprob, x))), 'k')
    plt.yticks([])
    plt.xlim(-5.5, 5.5)
    plt.ylabel('p(x)')
    cell1_output = plt.xlabel('x')
    if cell1_output is not None:
        print('cell1_output', cell1_output)
    return logprob

@print_ret
@memoize(group=group)
def cell2_moves(logprob):
    np.random.seed(589403)
    init = np.random.randn(32, 1)
    (nwalkers, ndim) = init.shape
    sampler0 = emcee.EnsembleSampler(nwalkers, ndim, logprob)
    sampler0.run_mcmc(init, 5000)
    cell2_output = print('Autocorrelation time: {0:.2f} steps'.format(sampler0.get_autocorr_time()[0]))
    if cell2_output is not None:
        print('cell2_output', cell2_output)
    return (nwalkers, sampler0, ndim, init)

@print_plt
@memoize(group=group)
def cell3_moves(sampler0):
    plt.plot(sampler0.get_chain()[:, 0, 0], 'k', lw=0.5)
    plt.xlim(0, 5000)
    plt.ylim(-5.5, 5.5)
    plt.title('move: StretchMove', fontsize=14)
    plt.xlabel('step number')
    cell3_output = plt.ylabel('x')
    if cell3_output is not None:
        print('cell3_output', cell3_output)

@print_plt
@memoize(group=group)
def cell4_moves(nwalkers, ndim, init, logprob):
    np.random.seed(93284)
    sampler = emcee.EnsembleSampler(nwalkers, ndim, logprob, moves=[(emcee.moves.DEMove(), 0.8), (emcee.moves.DESnookerMove(), 0.2)])
    sampler.run_mcmc(init, 5000)
    print('Autocorrelation time: {0:.2f} steps'.format(sampler.get_autocorr_time()[0]))
    plt.plot(sampler.get_chain()[:, 0, 0], 'k', lw=0.5)
    plt.xlim(0, 5000)
    plt.ylim(-5.5, 5.5)
    plt.title('move: [(DEMove, 0.8), (DESnookerMove, 0.2)]', fontsize=14)
    plt.xlabel('step number')
    cell4_output = plt.ylabel('x')
    if cell4_output is not None:
        print('cell4_output', cell4_output)

@memoize(group=group)
def main_moves():
    cell0_moves()
    logprob = cell1_moves()
    (nwalkers, sampler0, ndim, init) = cell2_moves(logprob)
    cell3_moves(sampler0)
    cell4_moves(nwalkers, ndim, init, logprob)

@memoize(group=group)
def cell0_parallel():
    """ %config InlineBackend.figure_format = "retina" """
    rcParams['savefig.dpi'] = 100
    rcParams['figure.dpi'] = 100
    rcParams['font.size'] = 20
    cell0_output = multiprocessing.set_start_method('fork')
    if cell0_output is not None:
        print('cell0_output', cell0_output)

@memoize(group=group)
def cell1_parallel():
    os.environ['OMP_NUM_THREADS'] = '1'

@print_ret
@memoize(group=group)
def log_prob(theta):
    t = time.time() + np.random.uniform(0.005, 0.008)
    while True:
        if time.time() >= t:
            break
    return -0.5 * np.sum(theta ** 2)

@print_ret
@memoize(group=group)
def cell3_parallel(log_prob):
    np.random.seed(42)
    initial = np.random.randn(32, 5)
    (nwalkers, ndim) = initial.shape
    nsteps = 100
    sampler = emcee.EnsembleSampler(nwalkers, ndim, log_prob)
    start = time.time()
    sampler.run_mcmc(initial, nsteps, progress=True)
    end = time.time()
    serial_time = end - start
    cell3_output = print('Serial took {0:.1f} seconds'.format(serial_time))
    if cell3_output is not None:
        print('cell3_output', cell3_output)
    return (nsteps, initial, nwalkers, ndim, serial_time)

@memoize(group=group)
def cell4_parallel(log_prob, nsteps, initial, nwalkers, ndim, serial_time):
    with Pool() as pool:
        sampler = emcee.EnsembleSampler(nwalkers, ndim, log_prob, pool=pool)
        start = time.time()
        sampler.run_mcmc(initial, nsteps, progress=True)
        end = time.time()
        multi_time = end - start
        print('Multiprocessing took {0:.1f} seconds'.format(multi_time))
        print('{0:.1f} times faster than serial'.format(serial_time / multi_time))

@memoize(group=group)
def cell5_parallel():
    ncpu = cpu_count()
    cell5_output = print('{0} CPUs'.format(ncpu))
    if cell5_output is not None:
        print('cell5_output', cell5_output)

@print_ret
@memoize(group=group)
def cell6_parallel(serial_time):
    with open('script.py', 'w') as f:
        f.write('\nimport sys\nimport time\nimport emcee\nimport numpy as np\nfrom schwimmbad import MPIPool\n\ndef log_prob(theta):\n    t = time.time() + np.random.uniform(0.005, 0.008)\n    while True:\n        if time.time() >= t:\n            break\n    return -0.5*np.sum(theta**2)\n\nwith MPIPool() as pool:\n    if not pool.is_master():\n        pool.wait()\n        sys.exit(0)\n        \n    np.random.seed(42)\n    initial = np.random.randn(32, 5)\n    nwalkers, ndim = initial.shape\n    nsteps = 100\n\n    sampler = emcee.EnsembleSampler(nwalkers, ndim, log_prob, pool=pool)\n    start = time.time()\n    sampler.run_mcmc(initial, nsteps)\n    end = time.time()\n    print(end - start)\n')
    mpi_time = 0
    mpi_time = float(mpi_time[0])
    print('MPI took {0:.1f} seconds'.format(mpi_time))
    cell6_output = print('{0:.1f} times faster than serial'.format(serial_time / mpi_time))
    if cell6_output is not None:
        print('cell6_output', cell6_output)

@print_ret
@memoize(group=group)
def log_prob_data(theta, data):
    a = data[0]
    t = time.time() + np.random.uniform(0.005, 0.008)
    while True:
        if time.time() >= t:
            break
    return -0.5 * np.sum(theta ** 2)

@print_ret
@memoize(group=group)
def cell7_parallel(initial, nwalkers, ndim, nsteps):
    data = np.random.randn(5000, 200)
    sampler = emcee.EnsembleSampler(nwalkers, ndim, log_prob_data, args=(data,))
    start = time.time()
    sampler.run_mcmc(initial, nsteps, progress=True)
    end = time.time()
    serial_data_time = end - start
    cell7_output = print('Serial took {0:.1f} seconds'.format(serial_data_time))
    if cell7_output is not None:
        print('cell7_output', cell7_output)
    return (log_prob_data, data, serial_data_time)

@memoize(group=group)
def cell8_parallel(log_prob_data, nsteps, initial, nwalkers, data, serial_data_time, ndim):
    with Pool() as pool:
        sampler = emcee.EnsembleSampler(nwalkers, ndim, log_prob_data, pool=pool, args=(data,))
        start = time.time()
        sampler.run_mcmc(initial, nsteps, progress=True)
        end = time.time()
        multi_data_time = end - start
        print('Multiprocessing took {0:.1f} seconds'.format(multi_data_time))
        print('{0:.1f} times faster(?) than serial'.format(serial_data_time / multi_data_time))

@print_ret
@memoize(group=group)
def log_prob_data_global(theta):
    a = data[0]
    t = time.time() + np.random.uniform(0.005, 0.008)
    while True:
        if time.time() >= t:
            break
    return -0.5 * np.sum(theta ** 2)

@memoize(group=group)
def cell9_parallel(nsteps, initial, nwalkers, data, serial_data_time, ndim):
    with Pool() as pool:
        sampler = emcee.EnsembleSampler(nwalkers, ndim, log_prob_data_global, pool=pool)
        start = time.time()
        sampler.run_mcmc(initial, nsteps, progress=True)
        end = time.time()
        multi_data_global_time = end - start
        print('Multiprocessing took {0:.1f} seconds'.format(multi_data_global_time))
        print('{0:.1f} times faster than serial'.format(serial_data_time / multi_data_global_time))

@memoize(group=group)
def main_parallel():
    cell0_parallel()
    cell1_parallel()
    (nsteps, initial, nwalkers, ndim, serial_time) = cell3_parallel(log_prob)
    cell4_parallel(log_prob, nsteps, initial, nwalkers, ndim, serial_time)
    cell5_parallel()
    cell6_parallel(serial_time)
    (log_prob_data, data, serial_data_time) = cell7_parallel(initial, nwalkers, ndim, nsteps)
    cell8_parallel(log_prob_data, nsteps, initial, nwalkers, data, serial_data_time, ndim)
    cell9_parallel(nsteps, initial, nwalkers, data, serial_data_time, ndim)

@memoize(group=group)
def cell0_quickstart():
    """ %config InlineBackend.figure_format = "retina" """
    rcParams['savefig.dpi'] = 100
    rcParams['figure.dpi'] = 100
    rcParams['font.size'] = 20

@print_ret
@memoize(group=group)
def log_prob(x, mu, cov):
    diff = x - mu
    return -0.5 * np.dot(diff, np.linalg.solve(cov, diff))

@print_ret
@memoize(group=group)
def cell3_quickstart():
    ndim = 5
    np.random.seed(42)
    means = np.random.rand(ndim)
    cov = 0.5 - np.random.rand(ndim ** 2).reshape((ndim, ndim))
    cov = np.triu(cov)
    cov += cov.T - np.diag(cov.diagonal())
    cov = np.dot(cov, cov)
    return (ndim, means, cov)

@print_ret
@memoize(group=group)
def cell4_quickstart(ndim):
    nwalkers = 32
    p0 = np.random.rand(nwalkers, ndim)
    return (nwalkers, p0)

@print_ret
@memoize(group=group)
def cell5_quickstart(log_prob, cov, means, nwalkers, ndim):
    sampler = emcee.EnsembleSampler(nwalkers, ndim, log_prob, args=[means, cov])
    return sampler

@memoize(group=group)
def cell6_quickstart(log_prob, cov, p0, means):
    cell6_output = log_prob(p0[0], means, cov)
    if cell6_output is not None:
        print('cell6_output', cell6_output)

@print_ret
@memoize(group=group)
def cell7_quickstart(sampler, p0):
    state = sampler.run_mcmc(p0, 100)
    cell7_output = sampler.reset()
    if cell7_output is not None:
        print('cell7_output', cell7_output)
    return state

@memoize(group=group)
def cell8_quickstart(state, sampler):
    cell8_output = sampler.run_mcmc(state, 10000)
    if cell8_output is not None:
        print('cell8_output', cell8_output)

@print_plt
@memoize(group=group)
def cell9_quickstart(sampler):
    samples = sampler.get_chain(flat=True)
    plt.hist(samples[:, 0], 100, color='k', histtype='step')
    plt.xlabel('$\\theta_1$')
    plt.ylabel('$p(\\theta_1)$')
    cell9_output = plt.gca().set_yticks([])
    if cell9_output is not None:
        print('cell9_output', cell9_output)

@memoize(group=group)
def cell10_quickstart(sampler):
    cell10_output = print('Mean acceptance fraction: {0:.3f}'.format(np.mean(sampler.acceptance_fraction)))
    if cell10_output is not None:
        print('cell10_output', cell10_output)

@memoize(group=group)
def cell11_quickstart(sampler):
    cell11_output = print('Mean autocorrelation time: {0:.3f} steps'.format(np.mean(sampler.get_autocorr_time())))
    if cell11_output is not None:
        print('cell11_output', cell11_output)

@memoize(group=group)
def main_quickstart():
    cell0_quickstart()
    (ndim, means, cov) = cell3_quickstart()
    (nwalkers, p0) = cell4_quickstart(ndim)
    sampler = cell5_quickstart(log_prob, cov, means, nwalkers, ndim)
    cell6_quickstart(log_prob, cov, p0, means)
    state = cell7_quickstart(sampler, p0)
    cell8_quickstart(state, sampler)
    cell9_quickstart(sampler)
    cell10_quickstart(sampler)
    cell11_quickstart(sampler)

if __name__ == '__main__':
    main_autocorr()
    main_line()
    main_monitor()
    main_moves()
    main_parallel()
    main_quickstart()
