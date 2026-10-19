# Project Plan

## Primary goal

Build a reproducible digital/product analytics platform that can move from raw event data to validated KPIs, experiment decisions, and causal measurement.

## Major workstreams

### 1. Event analytics
- GA4-style event schema
- sessions/users/events
- acquisition channels
- conversion events
- event validation

### 2. Product measurement
- KPI tree
- funnel conversion
- retention/cohorts
- customer journeys
- segmentation
- lead/revenue value

### 3. Experimentation
- randomization checks
- primary metric
- guardrail metrics
- hypothesis tests
- confidence intervals
- power analysis
- sample-size planning
- multiple-testing controls
- CUPED

### 4. Attribution
- last-touch baseline
- first-touch baseline
- multi-touch descriptive comparison
- explicit limitations

### 5. Causal measurement
Use Project 11 concepts where justified:
- treatment/outcome definitions
- covariate policy
- heterogeneous effects
- causal assumptions
- clear distinction between experiment estimates and observational analyses

### 6. BigQuery / SQL
SQL should calculate core analytics where appropriate. Python should independently validate important results.

## Non-goals

- Pretending synthetic clickstream data is real GA4 production data
- Treating attribution as causal proof
- Running dozens of unplanned subgroup tests and highlighting only significant ones
- Declaring a test successful solely from p < 0.05
