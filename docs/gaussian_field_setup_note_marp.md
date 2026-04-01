---
marp: true
theme: default
paginate: true
math: mathjax
---

# Gaussian-Field Dimensioning Setup

For a circular beam $\mathcal{B}\subset\mathbb{R}^2$,
$$
N \sim \mathrm{Poisson}(\lambda |\mathcal{B}|),
\qquad
X=\{x_i\}_{i=1}^N,
\qquad
x_i \stackrel{\mathrm{iid}}{\sim} \mathrm{Unif}(\mathcal{B}).
$$

Truth field:
$$
G^\star(x) \text{ = log-shadowing truth},
\qquad
S^\star(x)=e^{G^\star(x)}.
$$

Channel and demand:
$$
d(x)=\sqrt{h^2+r(x)^2},
\qquad
\mathrm{SNR}(x)=SNR_0\Bigl(\frac{d(x)}{h}\Bigr)^{-\gamma} e^{G(x)},
$$
$$
\eta(x)=\max\!\bigl(\eta_{\min},\log_2(1+\mathrm{SNR}(x))\bigr),
$$
$$
N_{\mathrm{RB}}(x)=
\left\lceil
\frac{c}{W_{\mathrm{RB}}\eta(x)}
\right\rceil,
\qquad
D(X,G)=\sum_{i=1}^N N_{\mathrm{RB}}(x_i).
$$

Required budget:
$$
B^\star
=
\min\Bigl\{
b \in \mathcal{G}_{\mathrm{RB}} :
\mathbb{P}\bigl(D(X,G^\star)>b\bigr)\le \varepsilon
\Bigr\}.
$$

---

# Setup Symbols

$$
\mathcal{B} : \text{beam footprint in } \mathbb{R}^2,
\qquad
| \mathcal{B} | : \text{beam area},
\qquad
\lambda : \text{PPP user intensity}.
$$

$$
N : \text{number of users in one trial},
\qquad
X=\{x_i\}_{i=1}^N : \text{user locations},
\qquad
x_i : \text{location of user } i.
$$

$$
G^\star(x) : \text{truth log-shadowing},
S^\star(x)=e^{G^\star(x)} : \text{truth linear shadowing factor},
$$

$$
h : \text{altitude},
\qquad
r(x) : \text{horizontal offset from beam center},
\qquad
d(x) : \text{slant range}.
$$

$$
SNR_0 : \text{reference SNR at } G=0,
\qquad
\gamma : \text{pathloss exponent},
\qquad
\eta_{\min} : \text{spectral-efficiency floor}.
$$

$$
c : \text{required user rate},
\qquad
W_{\mathrm{RB}} : \text{bandwidth per RB},
\qquad
N_{\mathrm{RB}}(x) : \text{user PRB demand},
\qquad
D(X,G) : \text{total beam PRB demand}.
$$

---

# Approximation Models

Uniform baseline:
$$
G_U(x_i)\stackrel{\mathrm{iid}}{\sim}\mathrm{Unif}[a,b].
$$

Gaussian-field model:
$$
G_G(X)\sim \mathcal{N}\!\bigl(\mu \mathbf{1},\,K_\theta(X)\bigr).
$$

RBF covariance family:
$$
\bigl[K_\theta(X)\bigr]_{ij}
=
\sigma^2
\exp\!\left(
-\frac{\|x_i-x_j\|^2}{2\ell^2}
\right).
$$

Moment calibration:
$$
\mu = \mathbb{E}_{x \sim \mathrm{Unif}(\mathcal{B})}[G^\star(x)],
\qquad
\sigma^2 = \mathrm{Var}_{x \sim \mathrm{Unif}(\mathcal{B})}[G^\star(x)].
$$

---

# Prediction and Comparison

Predicted total demand on one fixed PPP geometry:
$$
\widehat{D}_U(X)=\mathbb{E}[D(X,G_U)\mid X],
\qquad
\widehat{D}_G(X)=\mathbb{E}[D(X,G_G)\mid X].
$$

Trial-level comparison:
$$
e_U(X)=\bigl|D(X,G^\star)-\widehat{D}_U(X)\bigr|,
\qquad
e_G(X)=\bigl|D(X,G^\star)-\widehat{D}_G(X)\bigr|.
$$
$$
\text{Gaussian advantage on one trial}
\iff
e_G(X)<e_U(X).
$$

---

# Model Symbols

$$
G_U(x) : \text{uniform baseline field},
\qquad
G_G(x) : \text{Gaussian approximation field},
\qquad
S(x)=e^{G(x)} : \text{generic/model linear shadowing factor}.
$$

$$
a,b : \text{uniform interval endpoints},
\qquad
\mu : \text{field mean},
\qquad
\sigma^2 : \text{field variance}.
$$

$$
K_\theta(X) : \text{covariance matrix on the user set},
\qquad
\ell : \text{Gaussian correlation length},
\qquad
\theta : \text{kernel parameters}.
$$

$$
\widehat{D}_U(X),\widehat{D}_G(X) : \text{model-predicted total demands},
\qquad
e_U(X),e_G(X) : \text{trial-level absolute demand errors}.
$$

$$
\varepsilon : \text{outage target},
\qquad
\mathcal{G}_{\mathrm{RB}} : \text{candidate RB budget grid},
\qquad
B^\star : \text{truth required budget}.
$$

---

# Core Modeling Problem

Reference-truth requirement:
$$
G^\star \notin \mathcal{M}_G
\quad\text{if the claim is}\quad
\mathcal{M}_G \text{ is effective}.
$$

Problem 1: tautological truth
$$
G^\star \sim \mathcal{GP}(\mu^\star,K^\star)
\;\Longrightarrow\;
\mathcal{M}_G \text{ is advantaged by construction.}
$$

Problem 2: Gaussianized standards truth
$$
L_{\mathrm{ITU/3GPP}}(x)
\xrightarrow{\text{fit}}
\mathcal{N}(\mu_L,\sigma_L^2)
\;\Longrightarrow\;
G^\star \approx \text{Gaussianized marginal}
\;\Longrightarrow\;
\text{weak test of } \mathcal{M}_G.
$$

---

# Desired Truth and Objective

Desired smooth but non-tautological truth:
$$
G^\star(x)=T(Z(x)),
\qquad
Z \sim \mathcal{GP}(0,K^\star),
\qquad
T \text{ smooth, non-linear, non-Gaussian.}
$$

Examples:
$$
T(z)=\mu+\alpha \tanh(z),
\qquad
T(z)=\mu-\beta \log(1+e^z).
$$

Engineering objective:
$$
\mathbb{P}\!\left(D(X,G^\star)>B_G\right)\le \varepsilon
\quad\text{with small bias in } B_G-B^\star,
$$
not pointwise field reconstruction.

$$
B_G : \text{budget chosen by the Gaussian approximation model.}
$$

---

# Final Symbols

$$
\mathcal{M}_G : \text{Gaussian-field model family under evaluation},
\qquad
\mathcal{GP}(\mu^\star,K^\star) : \text{Gaussian-process truth law}.
$$

$$
\mu^\star : \text{truth mean function or level},
\qquad
K^\star : \text{truth covariance kernel or covariance operator}.
$$

$$
L_{\mathrm{ITU/3GPP}}(x) : \text{standards-based link-loss variable at location } x,
\qquad
\mu_L,\sigma_L^2 : \text{Gaussian-fit moments of that marginal}.
$$

$$
Z(x) : \text{latent smooth Gaussian field},
\qquad
T : \text{smooth non-linear transform used to define } G^\star.
$$

$$
\alpha,\beta : \text{transform amplitude parameters},
\qquad
B_G : \text{budget chosen by the Gaussian approximation},
\qquad
B^\star : \text{truth-side required budget}.
$$
