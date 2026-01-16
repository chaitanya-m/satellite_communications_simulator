# Kalman Filters

## Problem (single satellite, one object)

We want to learn the true satellite position from repeated, noisy position observations.

---

## Latent variable (the model)

Let  
$$
s \in \mathbb{R}^3
$$
be the **true satellite position** (unknown, fixed or slowly drifting).

This is the *state*.

---

## Prior belief (before a new observation)

From past observations, we maintain:
$$
s \sim \mathcal N(\mu,\Sigma)
$$

- $\mu$: current best estimate of the satellite position  
- $\Sigma$: uncertainty about that estimate  

This pair $(\mu,\Sigma)$ is the entire “Kalman state”.

---

## Observation (new data)

A new measurement produces an observed position:
$$
o = s + \varepsilon,\qquad \varepsilon \sim \mathcal N(0,R)
$$

- $o$: observed satellite position  
- $R$: observation noise (sensor error, atmospheric effects, etc.)

This defines the likelihood:
$$
p(o\mid s)=\mathcal N(o;s,R)
$$

---

## Bayesian update (the only inference step)

We apply Bayes’ rule:
$$
p(s\mid o)\propto p(o\mid s)\,p(s)
$$

Substitute the distributions:
$$
p(s\mid o)\propto
\mathcal N(o;s,R)\,
\mathcal N(s;\mu,\Sigma)
$$

This is a **product of two Gaussians in $s$**.

---

## Why this yields another Gaussian

The exponent of that product is quadratic in $s$.  
Any quadratic exponent corresponds to a Gaussian.

Therefore:
$$
s\mid o \sim \mathcal N(\mu^+,\Sigma^+)
$$

No approximation. This is exact.

---

## Closed-form solution (this is “Kalman”)

Define the **Kalman gain**:
$$
K=\Sigma(\Sigma+R)^{-1}
$$

Then:

Posterior mean:
$$
\mu^+ = \mu + K(o-\mu)
$$

Posterior covariance:
$$
\Sigma^+ = (I-K)\Sigma
$$

That is the entire update.

---

## What the Kalman gain really is

$K$ is the **Bayesian weight on the observation**.

- If $\Sigma \ll R$: trust prior $\rightarrow$ small update  
- If $\Sigma \gg R$: trust data $\rightarrow$ large update  

Equivalently:
$$
\mu^+ = (1-K)\mu + K o
$$

---

## Optional dynamics (between observations)

If the satellite position can drift:
$$
s_{t+1}=s_t+w_t,\quad w_t\sim\mathcal N(0,Q)
$$

Prediction step:
$$
\mu \leftarrow \mu
$$
$$
\Sigma \leftarrow \Sigma + Q
$$

If the satellite is static, set $Q=0$.

---

## Summary

A Kalman filter here is simply **repeated Bayesian updating of a Gaussian belief over a satellite position**, where the “Kalman gain” is just the uncertainty-based weight that upweights or downweights  new measurement data in Bayesian updates.

---

A linear Kalman filter is a Bayesian updater in which the strength of the update depends on the relative uncertainty of the prior and the new data point. “Linear” means that both the state transition model and the mapping from state to observation are linear functions of the state.

An extended Kalman filter allows a nonlinear state transition and a nonlinear mapping from state to observation. Because exact Bayesian updates are no longer tractable, it linearizes these nonlinear functions locally by computing their Jacobians (matrices of partial derivatives).

For the state prediction, it computes the Jacobian of the transition function 
$f(x)$ with respect to 
$x$ and uses this Jacobian to propagate uncertainty. For the observation update, it computes the Jacobian of the observation function 
$h(x)$ and uses it in the same Kalman update equations. The variance (covariance) updates are modified accordingly using these Jacobians.

Despite these changes, the underlying idea is unchanged: observations with high uncertainty contribute weakly to the update, while low-uncertainty observations contribute strongly.

# Poisson

An even arrival distribution that aims to model probability of a single event arrival as proportional to interval length $t$. As the time interval $t$ goes to 0, probability mass over the natural numbers for the distribution concentrates on 0 (no events at all). The distributions over time intervals are combined in a straightforward additive way.

# Optimal Transport 

The point map determines how mass moves, and the push‑forward is just the induced measure after that mass relocation. Mass is preserved during the move by construction via the push-forward constraint. The move doesn't have to be a bijection, it may be many-one. For instance, start with a uniform distribution over [0,1]. Move half the mass to [0,0.5]. Move the other half to [1]. This is obviously a many-one point mapping. The mass associated with the points (0.5,1] all goes to [1] - so the induced push-forward measure preserves mass.


Finding a mapping that optimises some cost function while inducing the push-forward is a difficult problem - which bit of mass goes where? Further, we may wish to model resource distribution as one-many.

Kantorovich optimises over a joint measure π on X×Y with marginals μ, ν, allowing mass‑splitting - using pairs means one-many is elegantly solved.
