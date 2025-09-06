# Notes

The strategies should optimize the probability of beating the current state-of-the-art;
i.e., we treat the best known score as a HARD CONSTRAINT, just like the venue size constraint (number of people accepted)
thus our goal is to find a policy that gives a feasible solution with the highest probability, regardless of the exact number of rejects

## Implementation

We're using Monte Carlo to estimate the probability of the problem being
feasible after the action (accept/reject).

For each run, we generate the counts of people of different types according to the estimated distribution:
$N+M$ people in total, where $N < 1000$ is the number of places left, and $M < 10000$ is the maximum number of rejections left;

Now the problem is reformulated as follows:

- $x_i$ -- $2^k$ non-negative integer variables, each is the count of *accepted*
  people of a given type
- 1 venue size constraint: $\sum_i x_i == N$,
- $k$ quota constraints: $\sum_{i \in a_j} x_i >= q_j$, where $a_j$ is the set of
  types of people that have attribute $j$, and $q_j$ is the corresponding
  attribute quota (deficits); $k <= 6$
- $2^k$ count constraint: $x_i <= c_i$, where $c_i$ is the count of people of type $i$
  in the given run

We check each run for feasibility, compare the esimates for both actions,
and finally choose the action that leads to the highest chance of the problem
being feasible.

## Clarifications

- `relative_frequencies` are the marginal probabilities of corresponding binary
  variables
- `MAX_REJECTIONS` in `strategy_base` contains current state-of-the-art per-scenario scores, i.e., number of rejections
