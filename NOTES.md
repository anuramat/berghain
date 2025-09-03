# Notes

The strategies should optimize the probability of beating the current state-of-the-art;
i.e., we treat the best known score as a HARD CONSTRAINT, just like the venue size constraint (number of people accepted)
thus our goal is to find a policy that gives a feasible solution with the highest probability, regardless of the exact number of rejects

## Clarifications

- `relative_frequencies` are the marginal probabilities of corresponding binary
  variables
- `MAX_REJECTIONS` in `strategy_base` contains current state-of-the-art per-scenario scores, i.e., number of rejections
