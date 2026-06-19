"""Pure-domain layer: clinical models and rules with NO Qt or DB dependency.

Everything here is unit-testable without a running Qt event loop or a database,
which keeps the clinically meaningful logic (habituation detection, graded
playlists, VAS scheduling, coping skills) reviewable in isolation.
"""
