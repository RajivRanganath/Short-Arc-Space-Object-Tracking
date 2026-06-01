# Notes: Orbit Determination with Very Short Arcs (Milani et al., 2008)

## Core Concept
We observe angular position (alpha, delta) and angular rates (alpha_dot, delta_dot).
We DO NOT know range (rho) or range-rate (rho_dot).

The "Admissible Region" K is the set of (rho, rho_dot) pairs that define a valid Earth orbit.

## Constraints
An orbit is "admissible" if:
1.  **Energy E < 0** (Bound orbit)
2.  **Pericenter distance q > R_earth** (Not crashing)

## Key Equations (Section 3)

### 1. Two-Body Energy Equation
E = (1/2)v^2 - mu/r
where:
- r = sqrt(rho^2 + R_obs^2 + ...)  (Law of cosines)
- v^2 = rho_dot^2 + rho^2(alpha_dot^2 + delta_dot^2) + ...

### 2. The Energy Constraint (E < 0)
Defines the outer boundary of our region.
If E >= 0, the object is flying away from Earth (hyperbola/parabola).

### 3. The Radius Constraint (r > R_earth)
Defines the inner "hole" of the region.
We cannot see through the Earth, so rho must be positive and r > 6378 km.

## Practical Application
When initializing the Particle Filter (EnKF):
1. Grid the (rho, rho_dot) plane.
2. Check each point against E < 0 and q > R_E.
3. Only sample particles from the valid region.
