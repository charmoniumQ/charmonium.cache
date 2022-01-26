import numpy as np

true_mu = 0.5
true_sd = 1
n_data = 3

y = true_mu + np.exp(true_sd) * np.random.randn(n_data)

import pymc3 as pm

with pm.Model() as model:
    mu = pm.Uniform("mu", lower=-5, upper=5)
    sd = pm.Uniform("sd", lower=-5, upper=5)

    pm.Normal("obs", mu=mu, sd=pm.math.exp(sd), observed=y)

    # trace = pm.sample(
    #     draws=10, tune=10, chains=2, cores=1, return_inferencedata=True
    # )
