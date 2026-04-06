---
marp: true
theme: default
paginate: true
math: mathjax
---

# Objective

We are building a fast RB-dimensioning surrogate for satellite systems.

The user provides:

- required user bit rate $c$
- outage target $\varepsilon$
- a one-point marginal channel law, preferably as a log-shadowing CDF $F_G$

If the starting point is a marginal SNR law rather than a log-shadowing law, it is converted upstream into an equivalent marginal $F_G$ under the fixed baseline/pathloss convention.

---

# Benchmark Question

The core benchmark question is:

- does a Gaussian spatial dependence surrogate produce better dimensioning values than an iid baseline
- when both models use the same one-point marginal $F_G$

---

# When Gaussian Should Win

- Gaussian should only help when spatial dependence matters for aggregate demand.
- The truth family must contain genuine spatial coherence across nearby users.
- The iid baseline must use the same marginal $F_G$, so the only difference is dependence.
- The truth generator should not itself be Gaussianized; otherwise the comparison becomes circular.

---

# Fair Comparison

- The iid baseline draws user shadowing iid from the supplied marginal $F_G$.
- The Gaussian surrogate keeps the same marginal $F_G$ at each user.
- The Gaussian surrogate adds only a dependence structure through a latent covariance model.
- Result: nearby users tend to receive more similar shadowing values, but the one-point law is unchanged.

---

# Current Research Focus

- Which scenario families give the Gaussian dependence model a clear advantage?
- Which scenario families make the iid baseline fail most clearly?

---

# Scope

- This question is methodological, not physical.
- Physics / telecom realism is not the point at this stage.
- The immediate goal is to identify which spatial-structure families favor the Gaussian dependence model.
- Standards-based realism can be layered in later, once that structural question is understood.

---

# User Workflow

- Input: required user bit rate $c$.
- Input: outage target $\varepsilon$.
- Input: one-point log-shadowing CDF $F_G$.
- Optional input: fixed beam / geometry assumptions used by the channel map.
- The user does not provide a spatial obstruction map, a covariance matrix, or a per-geometry simulation campaign.

---

# Online Model

- Sample user locations in the beam.
- Build an RBF covariance matrix on those user locations.
- Draw a latent Gaussian vector with correlation length $\ell$.
- Map that latent draw through the standard normal CDF and the quantile $F_G^{-1}$.
- Convert those draws to demand and estimate outage in order to choose the budget.

---

# Offline Calibration

- Offline studies are used to choose and justify the correlation length $\ell$.
- The supplied marginal $F_G$ fixes the one-point channel law.
- With the current fixed RBF kernel, ``correlation structure'' means essentially the choice of $\ell$.
- Online, the tool does not generate many obstruction scenarios.
- Online, it uses the validated $\ell$ to build one covariance matrix for the current user set, then samples that model repeatedly.

---

# Channel Setup

For a circular beam $\mathcal{B}\subset\mathbb{R}^2$,
$$
N \sim \mathrm{Poisson}(\lambda |\mathcal{B}|),
\qquad
X=\{x_i\}_{i=1}^{N},
\qquad
x_i \stackrel{\mathrm{iid}}{\sim} \mathrm{Unif}(\mathcal{B}).
$$

Let $G_0$ denote one-point log-shadowing at a generic user location. The user-supplied marginal law is
$$
G_0 \sim F_G.
$$

The channel map under any shadowing field $G(\cdot)$ is
$$
\mathrm{SNR}(x;G)=SNR_0\Bigl(\frac{d(x)}{h}\Bigr)^{-\gamma} e^{G(x)}.
$$

---

# Gaussian Dependence Engine

Latent Gaussian copula construction:
$$
Z(X)\sim \mathcal{N}\!\bigl(0,\,K_\ell(X)\bigr).
$$

With an RBF covariance family,
$$
\bigl[K_\ell(X)\bigr]_{ij}
=
\exp\!\left(
-\frac{\|x_i-x_j\|^2}{2\ell^2}
\right).
$$

Shared-marginal sampling:
$$
U_i=\Phi(Z_i),
\qquad
G_G(x_i)=F_G^{-1}(U_i).
$$

So each $G_G(x_i)$ has marginal law $F_G$, while dependence across users is induced by $K_\ell(X)$.

---

# Symbols

$$
\mathcal{B} : \text{beam footprint},
\qquad
\quad
x : \text{generic location in the beam},
\qquad
\lambda : \text{PPP user intensity},
\qquad
N : \text{user count},
\qquad
X=\{x_i\}_{i=1}^{N} : \text{user locations}.
$$

$$
G_0 : \text{generic one-point log-shadowing random variable},
\qquad
F_G : \text{CDF of the user-supplied one-point log-shadowing law},
\qquad
F_G^{-1} : \text{quantile function of } F_G.
$$

$$
Z(X) : \text{latent Gaussian vector over the sampled users},
\qquad
K_\ell(X) : \text{RBF covariance matrix on the user set},
\qquad
G_G(X) : \text{shared-marginal correlated shadowing values}.
$$

$$
\ell : \text{correlation length},
\qquad
\Phi : \text{standard normal CDF},
\qquad
U_i : \text{latent Gaussian percentile at user } i.
$$

---

# Channel to Demand Map

$$
d(x)=\sqrt{h^2+r(x)^2},
\qquad
\eta(x;G)=\max\!\bigl(\eta_{\min},\log_2(1+\mathrm{SNR}(x;G))\bigr).
$$

$$
N_{\mathrm{RB}}(x;G)=
\left\lceil
\frac{c}{W_{\mathrm{RB}}\eta(x;G)}
\right\rceil.
$$

$$
D(X,G)=\sum_{i=1}^{N} N_{\mathrm{RB}}(x_i;G).
$$

---

# Symbols

$$
d(x) : \text{slant range},
\qquad
h : \text{altitude},
\qquad
r(x) : \text{horizontal offset from beam center}.
$$

$$
SNR_0 : \text{reference SNR},
\qquad
\gamma : \text{pathloss exponent},
\qquad
G(\cdot) : \text{generic shadowing field over the beam}.
$$

$$
\mathrm{SNR}(x;G) : \text{SNR at location } x \text{ under field } G,
\qquad
\eta(x;G) : \text{effective spectral efficiency under field } G,
\qquad
\eta_{\min} : \text{spectral-efficiency floor}.
$$

$$
c : \text{required user bit rate},
\qquad
W_{\mathrm{RB}} : \text{bandwidth per RB},
\qquad
N_{\mathrm{RB}}(x;G) : \text{user RB demand under field } G.
$$

$$
D(X,G) : \text{total beam RB demand under field } G.
$$

---

# Dimensioning Output

The tool returns the smallest tested budget meeting the outage target:
$$
B_G
=
\min\Bigl\{
b \in \mathcal{G}_{\mathrm{RB}} :
\mathbb{P}\bigl(D(X,G_G)>b\bigr)\le \varepsilon
\Bigr\}.
$$

Product output:

- required RB budget
- optional derived capacity / satellite recommendation

---

# Why Gaussian Instead of iid Baseline

- The iid baseline draws $G_{\mathrm{iid}}(x_i)\stackrel{\mathrm{iid}}{\sim}F_G$.
- It matches the same one-point marginal law as the Gaussian surrogate.
- It ignores spatial dependence across nearby users.
- The Gaussian surrogate adds dependence only through the latent covariance matrix.

---

# What Is Validated Offline

- offline simulation is used to choose and validate the correlation structure
- not to drive the operator workflow
- the online tool uses the prevalidated Gaussian design directly
- the product claim is speed with acceptable dimensioning error

---

# Research Benchmark

To evaluate the Gaussian method, compare it against a benchmark truth field $G^\star(\cdot)$:
$$
B^\star
=
\min\Bigl\{
b \in \mathcal{G}_{\mathrm{RB}} :
\mathbb{P}\bigl(D(X,G^\star)>b\bigr)\le \varepsilon
\Bigr\}.
$$

The research question is:
$$
\text{is } B_G \text{ close enough to } B^\star \text{ to be operationally useful?}
$$

---

# Research Caution

If the benchmark truth is already Gaussian, the test is weak:
$$
G^\star \text{ is itself Gaussian}
\;\Longrightarrow\;
\text{Gaussian is advantaged by construction.}
$$

Likewise, if ITU-R / 3GPP inputs are first Gaussianized into a Gaussian shadowing truth, the benchmark is weakened.

So the evaluation truth should remain non-Gaussian when testing a Gaussian-field claim.

---

# Symbols

$$
G_{\mathrm{iid}} : \text{iid baseline shadowing field with marginal } F_G,
\qquad
G_G : \text{Gaussian surrogate shadowing field},
\qquad
G^\star : \text{benchmark truth shadowing field}.
$$

$$
\varepsilon : \text{outage target},
\qquad
\mathcal{G}_{\mathrm{RB}} : \text{candidate RB budget grid},
\qquad
b : \text{candidate RB budget}.
$$

$$
B_G : \text{Gaussian-model budget},
\qquad
B^\star : \text{benchmark truth budget}.
$$
