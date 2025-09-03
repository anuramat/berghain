- `relative_frequencies` are the marginal probabilities of corresponding binary
  variables
- `MAX_REJECTIONS` in `strategy_base` contains per-scenario maximum amount of
  rejections allowed; if you reject more than that -- you lost; effectively -- the
  resulting score is infinity, i.e. the worst possible score
