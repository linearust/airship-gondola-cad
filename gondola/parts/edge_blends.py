"""Explicit edge classes for small, protected native blends."""


def near(value, target):
    return abs(value - target) < 1e-6


def fillet_selected(shape, radius, predicate, expected, label):
    """Fail on changed topology instead of silently omitting a specified blend."""
    edges = [edge for edge in shape.Edges if predicate(edge, edge.BoundBox)]
    if len(edges) != expected:
        raise RuntimeError(f"{label}: expected {expected} edges, found {len(edges)}")
    result = shape.makeFillet(radius, edges).removeSplitter()
    if not result.isValid() or len(result.Solids) != 1:
        raise RuntimeError(f"{label}: blend must remain one valid solid")
    return result
