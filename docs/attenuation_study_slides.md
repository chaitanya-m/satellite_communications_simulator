# Attenuation Study Slides

This is a content-first slide deck for explaining the attenuation study to a
mixed or nontechnical audience. The goal is clarity, not visual polish. Each
slide includes:
- the main message;
- the exact slide content;
- speaker notes;
- a suggested visual.

The deck is deliberately plain-language. It avoids assuming that the audience
already understands outage, Gaussian fields, or Monte Carlo simulation.

---

## Slide 1 - Title

**Main message**

This work asks whether a Gaussian spatial model is good enough for RB
dimensioning under spatially structured attenuation.

**Slide content**

**Testing Gaussian Shadowing Models for Satellite RB Dimensioning**

- A shadowing model tells us how attenuation is distributed across users in the
  beam.
- That attenuation is turned into user SNR, then into PRBs needed per user,
  then into a total RB budget for the beam.
- Goal: decide whether a Gaussian field model gives a better RB-dimensioning
  model than a simple iid uniform-shadowing baseline.
- Context: satellite systems must choose enough resource blocks to meet demand
  without wasting capacity.
- Method: compare both models against explicit spatial obstruction scenarios.

**Speaker notes**

The audience needs the full chain immediately:
- the model describes spatial attenuation across users;
- attenuation determines SNR;
- SNR determines PRBs per user;
- summing across users gives the RB budget recommendation.

That makes the role of the model concrete on slide 1. The point is not just
"we ran simulations." The point is that different spatial attenuation models
can recommend different beam-wide RB budgets.

**Suggested visual**

One circular beam footprint with users inside it, plus the labels "Uniform
baseline", "Gaussian field", and "Ground truth obstruction".

---

## Slide 2 - What Is the Channel Model Here?

**Main message**

This study is intentionally not a full-physics telecom simulator. It is a
targeted model for one specific decision: RB dimensioning under spatially
structured attenuation.

**Slide content**

**What is the channel model in this work?**

In a full telecom stack, one link may include many effects:

- geometry and link budget;
- pathloss;
- shadowing / attenuation;
- small-scale fading;
- coding, modulation, scheduler details, and many other implementation effects.

This study deliberately keeps only the pieces needed for the question we are
asking:

- users are placed spatially in the beam;
- users experience location-dependent attenuation;
- attenuation changes SNR;
- SNR determines PRBs needed;
- total beam demand is aggregated across users.

What we keep:

- the spatial layout of users;
- the spatial layout of attenuation;
- the mapping from attenuation to demand.

What we deliberately leave out:

- extra realism that does not help answer the present question more clearly.
- any individual-user-equipment fading model that operates at a different
  level of abstraction from the beam-level dimensioning problem.

**Speaker notes**

This slide is the scope-defense slide. The key line is:

"A model should be judged against the question it is built to answer."

We are not claiming this is the most realistic end-to-end channel model. We are
claiming it is the right abstraction for isolating the effect of **spatial
attenuation structure** on **beam-wide RB dimensioning**.

For the realism-focused audience member, say explicitly:
- yes, more realism is possible;
- no, that is not automatically better for this study;
- adding realism that changes many mechanisms at once makes it harder to tell
  whether the Gaussian spatial assumption is helping or hurting.
- hyper-perfectionist realism is a risk here because it can muddy the causal
  question instead of sharpening it.
- this project is not going down to individual-user-equipment fading models;
  that is outside the scope of the work and outside the decision level being
  studied.

**Suggested visual**

Two boxes:

- **Full telecom reality**: many interacting effects
- **This study**: only the effects needed to test spatial attenuation impact on
  RB demand

with the second box highlighted as a deliberate experimental abstraction.

---

## Slide 3 - Why Nakagami Is Not Sufficient

**Main message**

More realism is not automatically better. Nakagami may be realistic for one
part of the channel, but it is not the mechanism this study is trying to test.

**Slide content**

**Why not just use a Nakagami distribution?**

Start with the fair definition:

- **Nakagami channel:** a probabilistic model for how the received signal
  amplitude of one radio link fluctuates, often used to represent different
  line-of-sight or multipath fading conditions.

That is a legitimate realism choice for a different study.

But here the main question is:

- if attenuation has spatial structure across the beam, does a Gaussian field
  approximation produce a better RB-dimensioning model than a simple iid
  baseline?

To answer that, we need to know:

- whether many users are jointly sitting in a bad region;
- whether the loss geometry is one large zone or many small clusters;
- whether nearby users share similar attenuation;
- how those spatial patterns change total beam demand.

Nakagami by itself does not specify that spatial structure.

So the right framing is:

- Nakagami belongs to a different modeling level;
- this project is not working at the individual-user-equipment fading level at
  all;
- bringing it in would move the work away from the beam-level spatial
  dimensioning question we are actually studying.
- **Why it is not the right model here:** our study is not about fluctuations
  of one link; it is about how attenuation is arranged across many users in the
  beam, because RB dimensioning depends on the joint spatial demand created by
  all users together.
- **Second rebuttal:** even if every user had a Nakagami link, we would still
  need a separate spatial attenuation model to say which users are jointly in
  blocked regions and how that changes total beam demand.

**Speaker notes**

This slide should politely but firmly push back on misplaced realism.

The strongest line is:

"Realism is only useful when it is realism in the mechanism under test."

Follow immediately with:

"A model should be judged against the question it is built to answer."

If someone asks why Nakagami is not used, the answer is:
- because Nakagami adds realism in single-link fading;
- this study is about realism in spatial attenuation structure;
- those are not the same thing.

If needed, say explicitly:
- this project does not go down to the individual-user-equipment fading level;
- that is not a missing detail here, it is a different study altogether.

If a stronger sentence is needed in the room, use:

"Adding every realistic detail is not rigor. If the added detail does not help
answer the question under test, it is just another way to blur the result."

**Suggested visual**

Left panel:
- "Single-link realism"
- one link with Nakagami fading

Right panel:
- "Beam-wide realism"
- many users under a structured attenuation map

Bottom caption:
- "This study focuses on beam-wide realism because that is what drives the
  decision under test."

---

## Slide 4 - Why This Work Exists

**Main message**

Wrong RB dimensioning has a real operational cost, so the shadowing model is
not an academic detail.

**Slide content**

**Why do this at all?**

- Satellite systems must choose an RB budget before knowing the exact user
  geometry and attenuation pattern of a given instant.
- If the budget is too small, users experience overload and poor service.
- If the budget is too large, scarce satellite resources are wasted.
- Shadowing is spatial: nearby users often experience similar attenuation.
- So the dimensioning result depends on the spatial model, not just on average
  loss.

**Speaker notes**

Now that the audience knows the modeling level, this slide can make the case
for existence cleanly. Start from the practical decision problem: "how many
RBs do we need?" Then explain that spatial structure changes that answer.

**Suggested visual**

Two boxes:
- Under-dimensioned -> overload / missed demand
- Over-dimensioned -> wasted capacity

---

## Slide 5 - The Gap

**Main message**

A simple iid baseline is easy but ignores spatial structure; a Gaussian field
adds correlation, but we do not know when that extra structure helps.

**Slide content**

**What is missing in current practice?**

- A simple baseline treats each user's shadowing independently.
- That ignores the fact that real attenuation often comes in spatial patterns:
  blocked regions, bands, and clusters.
- A Gaussian field model is a natural next step because it introduces spatial
  correlation.
- But correlation alone is not enough: we need to know whether it actually
  improves dimensioning decisions.

**Speaker notes**

The audience should leave this slide knowing the exact scientific gap:
"Does the Gaussian-field assumption improve the decision we care about?"

**Suggested visual**

Three mini-panels:
- iid random dots
- smooth Gaussian surface
- explicit structured obstruction map

---

## Slide 6 - Why Simulation Is Necessary

**Main message**

Simulation is necessary because the research question is about comparing
competing approximations against explicit spatial truth patterns.

**Slide content**

**Why simulation?**

- We are not asking for the performance of one assumed model.
- We are asking whether one approximation is better than another when the true
  attenuation pattern has spatial structure.
- If we started from one closed-form model and solved everything analytically,
  we would already be assuming the answer.
- Simulation lets us define controlled truth scenarios that are not forced to
  be uniform or Gaussian.
- Then we can test both candidate models against the same truth.

Example:

- suppose the true attenuation pattern is a large blocked square in the middle
  of the beam;
- now compare two approximations on that same truth:
  - iid uniform shadowing per user;
  - correlated Gaussian field shadowing.
- if we began by assuming a Gaussian field analytically, then the Gaussian
  assumption would already be built into the setup.
- simulation avoids that circularity: it lets us define the square-obstruction
  truth first, then ask which approximation is closer.

Plain-language summary:

- simulation is the tool that lets us separate **truth**, **approximation**,
  and **decision quality**.

**Speaker notes**

This should be an early anchor slide because it answers the most fundamental
objection directly. The audience needs to hear that simulation is not being
used because analysis is impossible or because we want pretty plots. It is
used because the scientific question is about model mismatch: we need a known
truth pattern, then we need to ask which approximation makes the better
dimensioning decision against that truth.

**Suggested visual**

One diagram with three layers:
- truth scenario
- competing models
- compare decisions

---

## Slide 7 - What Problem Simulation Solves

**Main message**

The goal is not just "simulate a channel." The goal is to test a dimensioning
decision under controlled spatial structure.

**Slide content**

**What simulation gives us that a closed-form model does not**

- A truth model with explicit spatial obstruction geometry.
- The same PPP user geometry fed to all compared models.
- A direct way to measure prediction error and dimensioning error.
- A controlled way to see where Gaussian structure helps and where it fails.

Without simulation, we would struggle to ask:

- What happens if the truth is a big blocked square?
- What happens if the truth is vertical bands?
- What happens if the truth is several local blocked circles?

These are exactly the cases we need in order to judge whether the Gaussian
field assumption is useful.

**Speaker notes**

This is the practical follow-up to the previous slide. The audience should now
understand that simulation is what creates the experimental control needed for
the comparison.

**Suggested visual**

Three truth scenarios on top, two model approximations below, one comparison
arrow to "better decision?".

---

## Slide 8 - Research Questions

**Main message**

The work is driven by two concrete questions.

**Slide content**

**Research questions**

1. Is a Gaussian field model better than an iid uniform-shadowing baseline for
   predicting demand and dimensioning RB budgets?
2. Does the answer depend on the spatial structure of the attenuation pattern?

Secondary question:

- Which obstruction patterns are captured well by a Gaussian field, and which
  ones are not?

**Speaker notes**

This keeps the story tight. It also stops the audience from thinking the goal
is "prove Gaussian is always best." That is not what the current results say.

**Suggested visual**

Simple question slide with bold keywords:
- better than uniform?
- depends on spatial pattern?

---

## Slide 9 - What We Compare

**Main message**

We compare two candidate models against an explicit truth model.

**Slide content**

**Three objects in the study**

- **Truth model:** deterministic obstruction scenarios placed inside a circular
  beam.
- **Uniform baseline:** each user gets an independent log-shadowing draw from a
  fixed interval.
- **Gaussian model:** users see a correlated Gaussian log-shadowing field.

Why this matters:

- the truth model defines what actually happens in the experiment;
- the uniform and Gaussian models are competing approximations.

**Speaker notes**

This slide is important because many people confuse the Gaussian model with the
truth model. Make it explicit: Gaussian is not "the answer"; it is one of the
candidate approximations being tested.

**Suggested visual**

Three columns labeled Truth / Uniform / Gaussian with one sentence under each.

---

## Slide 10 - One Trial, Step by Step

**Main message**

A single trial is easy to understand if presented as a fixed sequence.

**Slide content**

**How one trial works**

1. Sample user positions in the circular beam using a spatial PPP.
2. Evaluate the chosen obstruction scenario on those user positions.
3. Convert the resulting shadowing values into per-user PRB demand.
4. Sum across users to get the true total demand for that instant.
5. On that same fixed user geometry, ask the uniform and Gaussian models what
   total demand they would predict.
6. Compare model prediction errors on that trial.

**Speaker notes**

This is the first slide where the simulation should feel concrete. Say "one
trial means one realized user geometry and one realized truth-side demand."
Keep it procedural.

**Suggested visual**

Flowchart:
PPP users -> obstruction evaluation -> PRB demand -> total demand -> compare
uniform and Gaussian predictions

---

## Slide 11 - Where the Randomness Comes From

**Main message**

There are two layers of randomness, and confusing them makes the whole method
 hard to follow.

**Slide content**

**Two layers of randomness**

- **Outer randomness:** each trial uses a new PPP user geometry.
- **Inner randomness:** on one fixed geometry, the uniform and Gaussian models
  are still random because they draw shadowing values.

In the current truth model:

- once the user geometry is fixed, the obstruction pattern is deterministic;
- only the model-side predictions remain random.

This is why we use repeated inner prediction draws on one fixed geometry.

**Speaker notes**

This slide is essential because this was the main source of confusion earlier.
Explain it slowly:
- outer loop = new world;
- inner loop = repeated model guesses for the same world.

**Suggested visual**

One outer loop box containing a fixed beam picture, and inside it two smaller
boxes labeled "10 uniform draws" and "10 Gaussian draws".

---

## Slide 12 - What an Inner Prediction Draw Means

**Main message**

The inner draws estimate what each model typically predicts on one fixed trial.

**Slide content**

**Inner prediction draws**

For one fixed PPP geometry:

- draw the uniform model multiple times;
- draw the Gaussian model multiple times;
- average total demand within each model;
- compare those two averages to the one true realized demand.

In the current research setup:

- 10 seeds
- 100 trials per seed-scenario
- 10 inner prediction draws per trial

**Speaker notes**

This is the plain-language explanation of the Monte Carlo procedure. The goal
is not to overwhelm the audience with statistics. The goal is to make it clear
that the model is being evaluated on repeated guesses for the same fixed
geometry.

**Suggested visual**

One truth value on the left, then two stacks of 10 model draws averaged into
one value each.

---

## Slide 13 - Obstruction Scenarios

**Main message**

We do not test one generic "shadowing pattern." We test several distinct
spatial structures.

**Slide content**

**Ground-truth obstruction scenarios**

- **Centered square:** one large blocked region in the middle of the beam.
- **Vertical bands:** large strip-like regions crossing the beam.
- **Multiple circles:** several separated local blocked regions.

Why these matter:

- they represent qualitatively different spatial structures;
- a model that works for one structure may fail on another.

**Speaker notes**

This slide sets up the most important result later: Gaussian does not behave
the same way on all scenario types.

**Suggested visual**

Three beam diagrams side by side:
- square center
- vertical bands
- multiple circles

---

## Slide 14 - First Research-Scale Setup

**Main message**

The initial study case is already large enough to be operationally meaningful.

**Slide content**

**Current research-scale setup**

- Beam radius: 10
- Beam area: about 314
- PPP intensity: 1 user per unit area
- Expected users per trial: about 314
- PRB cap per user: 10
- Budget grid: 500 to 6000
- Seeds: 10
- Trials per seed-scenario: 100
- Inner prediction draws per trial: 10

Total trial-level comparisons in the pooled certificate:

- 3 scenarios x 10 seeds x 100 trials = 3000 comparisons

**Speaker notes**

This is where you reassure the audience that the study is not just a toy.
Several hundred users per trial is already meaningful, and the setup is
explicit enough to be reproducible.

**Suggested visual**

Small parameter table.

---

## Slide 15 - What We Measure

**Main message**

We measure two different things, and they answer different questions.

**Slide content**

**Two outputs**

1. **Budget-level output**
   - Estimate overload frequency across an RB budget grid.
   - Choose the smallest budget that meets the outage target.

2. **Trial-level certificate**
   - On each trial, ask which model predicts total demand more accurately.
   - Record a success if Gaussian error is smaller than uniform error.
   - Aggregate those successes into a statistical certificate.

**Speaker notes**

This is where you prevent a second common confusion: required-budget results
and per-trial prediction certificates are related, but they are not the same
object.

**Suggested visual**

Split slide:
- left = budget decision
- right = Bernoulli success/failure tally

---

## Slide 16 - First Results

**Main message**

The first result is not "Gaussian always wins." The result is more interesting
than that.

**Slide content**

**Scenario-by-scenario results**

| Scenario | Gaussian better rate | Certified? | Mean abs. error (Uniform) | Mean abs. error (Gaussian) |
|---|---:|---:|---:|---:|
| Square center | 0.999 | Yes | 678.54 | 591.09 |
| Vertical bands | 0.999 | Yes | 682.18 | 594.73 |
| Multi circles | 0.001 | No | 133.96 | 221.40 |

Pooled across all three scenarios:

- Gaussian successes: 1999 / 3000
- Estimated success probability: 0.6663
- Lower confidence bound: 0.6440
- Pooled certificate: Yes

**Speaker notes**

This is the slide to pause on. The pooled result says Gaussian wins overall,
but the scenario breakdown says the story is structural:
- Gaussian is excellent on large contiguous patterns;
- Gaussian is poor on fragmented circle patterns.

That is a much stronger and more honest scientific message than "Gaussian is
better."

**Suggested visual**

Table plus a one-line takeaway box:
"Gaussian helps on large smooth structures, not on all structures."

---

## Slide 17 - Interpretation

**Main message**

The value of the work is that it shows when Gaussian structure helps and when
it breaks.

**Slide content**

**What do these results mean?**

- The Gaussian field model captures broad, spatially coherent attenuation
  patterns well.
- It does not automatically capture fragmented or highly localized patterns.
- So model choice should depend on obstruction geometry, not just on average
  attenuation level.
- This justifies the work: we need a disciplined way to test whether a spatial
  model is actually appropriate for dimensioning.

**Speaker notes**

This is the real scientific contribution slide. It turns the results into a
reason the work matters.

**Suggested visual**

Two green check marks under square/bands and one red X under circles.

---

## Slide 18 - What Is New Here

**Main message**

This work contributes a testable evaluation framework, not just another
simulation.

**Slide content**

**What is in this work?**

- A clear truth-vs-model comparison setup.
- Explicit spatial obstruction scenarios.
- A repeated-trial RB-dimensioning pipeline.
- A trial-level statistical certificate comparing Gaussian and uniform.
- Reproducible research-scale tests with structured outputs.

**Speaker notes**

This slide helps the audience understand that the contribution is not just one
numerical result. The contribution is also the method and the experimental
discipline.

**Suggested visual**

Checklist of deliverables.

---

## Slide 19 - Why It Matters

**Main message**

The work matters because it moves model choice from assumption to evidence.

**Slide content**

**Why this matters**

- Satellite RB dimensioning depends on uncertainty in spatial attenuation.
- Simple baselines may miss important spatial structure.
- More expressive models are only useful if they improve the actual decision.
- This work provides an evidence-based way to decide when a Gaussian spatial
  model is worth using.

**Speaker notes**

End by returning to the decision problem, not the simulation details.

**Suggested visual**

One closing sentence centered on the slide:
"Do not choose the spatial model by convenience; choose it by evidence."

---

## Slide 20 - Next Steps

**Main message**

The current result is a first case, not the end of the study.

**Slide content**

**Next steps**

- Sweep Gaussian parameterizations more systematically.
- Vary obstruction strength, not just obstruction geometry.
- Increase the scale from a few hundred to a few thousand expected users.
- Compare dimensioning decisions directly, not only prediction accuracy.
- Add plots and scenario visuals for the paper and talk.

**Speaker notes**

This slide prevents the audience from thinking the work is over. It is a first
research-scale case with a strong early message.

**Suggested visual**

Simple roadmap arrow with 3 to 5 milestones.

---

## Backup Slide - One-Sentence Summary

**Slide content**

We built a reproducible experiment that tests whether Gaussian spatial
shadowing models actually improve satellite RB dimensioning, and the first
result is that they help on large coherent obstruction patterns but fail on
fragmented multi-circle patterns.
