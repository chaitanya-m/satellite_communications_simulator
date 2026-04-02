---
marp: true
theme: default
paginate: true
math: mathjax
---

# Gaussian-Field Dimensioning

- User goal: get a dimensioning value quickly.
- User does not want to run a large scenario library online.
- Product input is compact: rate target, outage target, and a marginal SNR distribution.
- Product output is a required RB budget or capacity recommendation.

---

# User Workflow

- Input: required user bit rate $c$.
- Input: outage target $\varepsilon$.
- Input: marginal SNR distribution $F_{\Gamma}$.
- Input: beam / load assumptions.

---

# What the Tool Does

- Build one Gaussian field model from the supplied marginal SNR information.
- Use an RBF covariance model over the sampled user positions.
- In the current model, the main spatial parameter is the correlation length $\ell$.
- Draw many correlated shadowing realizations from that same Gaussian model.
- Convert those draws to demand and estimate outage in order to choose the budget.

---

# What Is Fixed Offline

- Offline studies are used to choose and justify the correlation length $\ell$.
- Mean and variance come mainly from the supplied marginal SNR distribution.
- With the current fixed RBF kernel, ``correlation structure'' means essentially the choice of $\ell$.
- Online, the tool does not generate many obstruction scenarios.
- Online, it uses the validated $\ell$ to build one covariance matrix for the current user set, then samples that model repeatedly.

---

# What the User Does Not Provide

- no spatial obstruction map
- no covariance matrix
- no scenario family or descriptor model
- no per-geometry simulation campaign

---

# Mathematical Setup

For a circular beam $\mathcal{B}\subset\mathbb{R}^2$,
$$
N \sim \mathrm{Poisson}(\lambda |\mathcal{B}|),
\qquad
X=\{x_i\}_{i=1}^{N},
\qquad
x_i \stackrel{\mathrm{iid}}{\sim} \mathrm{Unif}(\mathcal{B}).
$$

If $\Gamma(x)$ denotes user SNR, the user supplies its marginal law
$$
\Gamma(x) \sim F_{\Gamma}.
$$

Equivalent shadowing representation:
$$
G(x)=\log \Gamma(x)-\log SNR_0+\gamma\log\!\Bigl(\frac{d(x)}{h}\Bigr).
$$

---

# Gaussian Engine

The tool builds a Gaussian field over the sampled users:
$$
G_G(X)\sim \mathcal{N}\!\bigl(\mu \mathbf{1},\,K_\theta(X)\bigr).
$$

With an RBF covariance family,
$$
\bigl[K_\theta(X)\bigr]_{ij}
=
\sigma^2
\exp\!\left(
-\frac{\|x_i-x_j\|^2}{2\ell^2}
\right).
$$

Here:
$$
\theta=(\mu,\sigma^2,\ell).
$$

---

# Symbols

$$
\mathcal{B} : \text{beam footprint},
\qquad
\lambda : \text{PPP user intensity},
\qquad
N : \text{user count},
\qquad
X=\{x_i\}_{i=1}^{N} : \text{user locations}.
$$

$$
F_{\Gamma} : \text{marginal SNR distribution supplied by the user},
\qquad
G_G(X) : \text{Gaussian field over the sampled users}.
$$

$$
K_\theta(X) : \text{covariance matrix on the user set},
\qquad
\theta=(\mu,\sigma^2,\ell) : \text{Gaussian parameters}.
$$

$$
\mu : \text{field mean},
\qquad
\sigma^2 : \text{field variance},
\qquad
\ell : \text{correlation length}.
$$

---

# Channel and Demand

$$
d(x)=\sqrt{h^2+r(x)^2},
\qquad
\mathrm{SNR}(x)=SNR_0\Bigl(\frac{d(x)}{h}\Bigr)^{-\gamma} e^{G_G(x)}.
$$

$$
\eta(x)=\max\!\bigl(\eta_{\min},\log_2(1+\mathrm{SNR}(x))\bigr).
$$

$$
N_{\mathrm{RB}}(x)=
\left\lceil
\frac{c}{W_{\mathrm{RB}}\eta(x)}
\right\rceil,
\qquad
D(X,G_G)=\sum_{i=1}^{N} N_{\mathrm{RB}}(x_i).
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
G_G(x) : \text{Gaussian-field log-shadowing}.
$$

$$
\eta(x) : \text{effective spectral efficiency},
\qquad
\eta_{\min} : \text{spectral-efficiency floor}.
$$

$$
c : \text{required user bit rate},
\qquad
W_{\mathrm{RB}} : \text{bandwidth per RB},
\qquad
N_{\mathrm{RB}}(x) : \text{user PRB demand}.
$$

$$
D(X,G_G) : \text{total beam PRB demand under the Gaussian model}.
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

# Why Gaussian Instead of iid Uniform

- iid Uniform matches only a marginal law.
- It ignores spatial dependence across nearby users.
- A Gaussian field couples nearby users through covariance.
- That covariance should improve aggregate demand and outage prediction.

---

# What Is Validated Offline

- offline simulation is used to choose and validate the correlation structure
- not to drive the operator workflow
- the online tool uses the prevalidated Gaussian design directly
- the product claim is speed with acceptable dimensioning error

---

# Research Benchmark

To evaluate the Gaussian method, compare it against a benchmark truth:
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
G^\star \sim \mathcal{GP}(\mu^\star,K^\star)
\;\Longrightarrow\;
\text{Gaussian is advantaged by construction.}
$$

Likewise, if ITU-R / 3GPP inputs are first Gaussianized into a Gaussian shadowing truth, the benchmark is weakened.

So the evaluation truth should remain non-Gaussian when testing a Gaussian-field claim.

---

# Symbols

$$
\mathcal{B} : \text{beam footprint},
\quad
\lambda : \text{PPP user intensity},
\quad
X=\{x_i\}_{i=1}^{N} : \text{user locations},
\quad
N : \text{user count}.
$$

$$
F_{\Gamma} : \text{marginal SNR distribution},
\quad
G_G : \text{Gaussian shadowing field},
\quad
\theta=(\mu,\sigma^2,\ell) : \text{Gaussian parameters}.
$$

$$
c : \text{required user bit rate},
\quad
\varepsilon : \text{outage target},
\quad
\mathcal{G}_{\mathrm{RB}} : \text{candidate RB budget grid}.
$$

$$
B_G : \text{Gaussian-model budget},
\quad
B^\star : \text{benchmark truth budget}.
$$
