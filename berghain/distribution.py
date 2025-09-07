from __future__ import annotations

import numpy as np
from typing import Dict, FrozenSet


def _generate_attribute_patterns(attributes: tuple[str, ...]) -> tuple[frozenset[str], ...]:
    """Generate all 2^k possible attribute combinations."""
    k = len(attributes)
    patterns = []
    for i in range(2**k):
        pattern = frozenset(
            attributes[j] for j in range(k) if (i >> j) & 1
        )
        patterns.append(pattern)
    return tuple(patterns)


def _pattern_to_binary(pattern: frozenset[str], attributes: tuple[str, ...]) -> np.ndarray:
    """Convert pattern to binary vector."""
    return np.array([attr in pattern for attr in attributes], dtype=float)


def _compute_marginals_from_proba(proba: np.ndarray, attributes: tuple[str, ...]) -> dict[str, float]:
    """Compute marginal probabilities from joint distribution."""
    marginals = {}
    k = len(attributes)
    
    for j, attr in enumerate(attributes):
        marginal = 0.0
        for i in range(2**k):
            if (i >> j) & 1:  # attribute j is present in pattern i
                marginal += proba[i]
        marginals[attr] = marginal
    
    return marginals


def _compute_correlations_from_proba(proba: np.ndarray, attributes: tuple[str, ...]) -> dict[str, dict[str, float]]:
    """Compute pairwise correlations from joint distribution."""
    k = len(attributes)
    correlations = {}
    
    # First compute marginals
    marginals = _compute_marginals_from_proba(proba, attributes)
    
    for i, attr1 in enumerate(attributes):
        correlations[attr1] = {}
        for j, attr2 in enumerate(attributes):
            if i == j:
                correlations[attr1][attr2] = 1.0
                continue
                
            # Compute joint probability P(attr1=1, attr2=1)
            joint = 0.0
            for pattern_idx in range(2**k):
                if ((pattern_idx >> i) & 1) and ((pattern_idx >> j) & 1):
                    joint += proba[pattern_idx]
            
            # Compute correlation coefficient
            p1, p2 = marginals[attr1], marginals[attr2]
            covariance = joint - p1 * p2
            correlation = covariance / np.sqrt(p1 * (1 - p1) * p2 * (1 - p2))
            correlations[attr1][attr2] = correlation
    
    return correlations


def maxent_from_constraints(
    marginals: dict[str, float],
    correlations: dict[str, dict[str, float]]
) -> tuple[np.ndarray, tuple[str, ...], tuple[frozenset[str], ...]]:
    """Create maximum entropy distribution from marginal constraints (simplified version)."""
    attributes = tuple(sorted(marginals.keys()))
    patterns = _generate_attribute_patterns(attributes)
    k = len(attributes)
    
    # Simple approach: start with uniform and iteratively adjust for marginals
    proba = np.ones(2**k) / (2**k)
    
    # Iteratively adjust probabilities to match marginals
    for _ in range(50):  # max iterations
        # Check current marginals
        current_marginals = _compute_marginals_from_proba(proba, attributes)
        
        # Check if we're close enough
        marginal_error = max(
            abs(current_marginals[attr] - marginals[attr]) 
            for attr in attributes
        )
        if marginal_error < 1e-6:
            break
            
        # Adjust probabilities using iterative scaling
        for j, attr in enumerate(attributes):
            target_marginal = marginals[attr]
            current_marginal = current_marginals[attr]
            
            if current_marginal > 1e-10:  # avoid division by zero
                scale_factor = target_marginal / current_marginal
                
                # Apply scaling to all patterns containing this attribute
                for i in range(2**k):
                    if (i >> j) & 1:  # attribute j present
                        proba[i] *= scale_factor
                
                # Renormalize to prevent drift
                if proba.sum() > 1e-10:
                    proba = proba / proba.sum()
                else:
                    # Reset if we get numerical issues
                    proba = np.ones(2**k) / (2**k)
                    break
                    
                current_marginals = _compute_marginals_from_proba(proba, attributes)
    
    return proba, attributes, patterns


def update_with_observation(
    proba: np.ndarray,
    observation_pattern: frozenset[str],
    patterns: tuple[frozenset[str], ...],
    learning_rate: float = 0.01
) -> np.ndarray:
    """Update distribution with single observation using exponential update."""
    # Find pattern index
    try:
        obs_idx = patterns.index(observation_pattern)
    except ValueError:
        return proba  # Pattern not found, no update
    
    # Exponential update
    new_proba = proba.copy()
    new_proba[obs_idx] *= (1 + learning_rate)
    
    # Renormalize
    new_proba = new_proba / new_proba.sum()
    
    return new_proba


def project_to_constraints(
    proba: np.ndarray,
    target_marginals: dict[str, float],
    target_correlations: dict[str, dict[str, float]],
    attributes: tuple[str, ...],
    max_iterations: int = 10,
    tolerance: float = 1e-4
) -> np.ndarray:
    """Project distribution back to satisfy marginal constraints using iterative scaling."""
    k = len(attributes)
    current_proba = proba.copy()
    
    # Ensure probabilities are positive and normalized
    current_proba = np.maximum(current_proba, 1e-10)
    if current_proba.sum() > 1e-10:
        current_proba = current_proba / current_proba.sum()
    else:
        current_proba = np.ones(2**k) / (2**k)
    
    for iteration in range(max_iterations):
        # Check convergence
        current_marginals = _compute_marginals_from_proba(current_proba, attributes)
        marginal_error = max(
            abs(current_marginals[attr] - target_marginals[attr]) 
            for attr in attributes
        )
        
        if marginal_error < tolerance:
            break
            
        # Update to match marginals (Sinkhorn-like scaling)
        for j, attr in enumerate(attributes):
            target_marginal = target_marginals[attr]
            current_marginal = current_marginals[attr]
            
            if current_marginal > 1e-10:  # avoid division by zero
                scale_factor = target_marginal / current_marginal
                
                # Apply scaling to all patterns containing this attribute
                for i in range(2**k):
                    if (i >> j) & 1:  # attribute j present
                        current_proba[i] *= scale_factor
                
                # Renormalize with safety check
                if current_proba.sum() > 1e-10:
                    current_proba = current_proba / current_proba.sum()
                else:
                    # Reset if numerical issues
                    current_proba = np.ones(2**k) / (2**k)
                    break
    
    return current_proba


class OnlineDistribution:
    """Manages online learning of joint distribution with constraint preservation."""
    
    def __init__(
        self,
        marginals: dict[str, float],
        correlations: dict[str, dict[str, float]]
    ):
        self.target_marginals = marginals.copy()
        self.target_correlations = correlations.copy()
        
        # Initialize with maximum entropy distribution
        self.proba, self.attributes, self.patterns = maxent_from_constraints(
            marginals, correlations
        )
        
        # Create bits_to_set for compatibility with existing code
        self.bits_to_set = self.patterns
        
        self.n_observations = 0
    
    def update(self, person_attrs: dict[str, bool]) -> None:
        """Update distribution with new observation."""
        # Convert person attributes to pattern
        pattern = frozenset(attr for attr, value in person_attrs.items() if value)
        
        # Use a small, decaying learning rate to avoid instability
        learning_rate = 0.01 / (1 + self.n_observations * 0.001)
        
        # Update with observation
        self.proba = update_with_observation(
            self.proba, pattern, self.patterns, learning_rate=learning_rate
        )
        
        # Project back to constraints (only every few updates to save computation)
        if self.n_observations % 5 == 0:
            self.proba = project_to_constraints(
                self.proba, self.target_marginals, self.target_correlations, self.attributes
            )
        
        self.n_observations += 1
    
    def get_proba(self) -> np.ndarray:
        """Get current probability distribution."""
        return self.proba.copy()