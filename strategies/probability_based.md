# Probability-Based Strategy

## Overview

This strategy optimally balances constraint satisfaction with rejection budget management using statistical reasoning. The core insight is that we should be more selective when we have rejection budget remaining and less selective as we approach our limits.

## Mathematical Foundation

### Expected Value Calculation

Given marginal probabilities P(attribute) and remaining slots, we can calculate the expected number of people with each attribute:

```
E[remaining_with_attribute] = remaining_slots × P(attribute)
```

### Urgency Metric

For each constraint, we calculate an urgency score that represents how critically we need that attribute:

```
urgency = remaining_needed / expected_remaining

where:
- remaining_needed = min_required[attribute] - current_admitted[attribute]  
- expected_remaining = remaining_slots × P(attribute)
```

When expected_remaining < 1, urgency is set to a high value (10.0) to ensure we don't miss rare opportunities.

## Scoring System

### Attribute Urgency Score

Each person receives a score based on their attributes:
- For each true attribute that we need for constraints, add the urgency score
- This ensures we prioritize people who help us meet our most difficult constraints

### Correlation Bonuses

People with multiple positively correlated desirable attributes receive bonus points:
- For each pair of true attributes (attr1, attr2) where both are needed for constraints
- Add correlation(attr1, attr2) × 0.1 to the score
- This recognizes that some people are especially valuable because their attributes tend to cluster

## Dynamic Threshold

The acceptance threshold adapts based on two pressure metrics:

```
rejection_pressure = current_rejections / max_rejections
capacity_pressure = current_admitted / 1000
pressure = max(rejection_pressure, capacity_pressure)
threshold = base_threshold × (1 - pressure)²
```

The quadratic decay ensures:
- Early game: High selectivity (threshold ≈ 1.0)
- Mid game: Moderate selectivity as pressure builds
- Late game: Very low selectivity to ensure venue fills

## Strategic Logic

1. **Early Phase**: With full rejection budget, we can afford to wait for ideal candidates who strongly help our constraints

2. **Middle Phase**: As rejection pressure builds, we gradually lower standards while still prioritizing constrained attributes

3. **Late Phase**: As we approach rejection limits or venue capacity, we become much less selective to ensure completion

4. **Constraint Priority**: People helping with the most urgent constraints (low expected remaining) get highest priority

5. **Correlation Exploitation**: People with multiple beneficial attributes get bonus consideration since they're statistically rarer and more valuable

## Why This Works

- **Budget-Aware**: Uses rejection budget efficiently by being selective early and permissive late
- **Data-Driven**: Leverages actual probabilities rather than heuristics  
- **Constraint-Focused**: Prioritizes the most difficult-to-satisfy constraints
- **Adaptive**: Responds to actual game state rather than following a fixed rule
- **Statistically Sound**: Based on expected value calculations that account for remaining opportunities