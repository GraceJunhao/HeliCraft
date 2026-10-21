"""Versioned full-domain, cell-centred sampling. No collision filtering."""
import math
import numpy as np

SAMPLING_VERSION = 'surface-grid-v2'
MAX_COPIES = 50000
MAX_ATOMS = 2000000
FAMILIES = ('圆柱状螺旋', '锥形螺旋', '阿基米德螺旋', '斐波那契螺旋', 'Flat带', 'Twist带')


def family_of(name):
    for family in FAMILIES:
        if name in (family, '右旋' + family, '左旋' + family):
            return family
    raise ValueError('Unsupported scaffold family.')


def radial_profile(family, p, t):
    if family == FAMILIES[0]:
        return np.full_like(t, p['R']), np.zeros_like(t)
    if family == FAMILIES[1]:
        slope = (p['Rtop'] - p['Rbase']) / (2 * math.pi * p['N'])
        return p['Rbase'] + slope * t, np.full_like(t, slope)
    if family == FAMILIES[2]:
        return p['Rbase'] + p['k'] * t, np.full_like(t, p['k'])
    growth = math.log((1 + math.sqrt(5)) / 2) / (2 * math.pi)
    radius = p['Rbase'] * np.exp(growth * t)
    return radius, growth * radius


def projected_arclength(family, p):
    # Fixed deterministic quadrature; integral of |dc/dt cross ez|.
    # W is GLOBAL-Z width, so P does not enter this surface-area Jacobian.
    t = np.linspace(0, 2 * math.pi * p['N'], 8193)
    r, dr = radial_profile(family, p, t)
    speed = np.hypot(r, dr)
    cumulative = np.concatenate(([0.], np.cumsum((speed[1:] + speed[:-1]) * np.diff(t) / 2)))
    return t, cumulative


def sampling_plan(name, p, atom_count=None):
    family = family_of(name)
    w, spacing = p['W'], p['L']
    ribbon = family in FAMILIES[4:]
    if ribbon:
        span = p['Length']
        # Keep the already corrected ribbon cell grid stable.
        nw, nt = max(1, int(w / spacing)), max(1, int(span / spacing))
        measure = 'ribbon parameter-domain area; not twisted surface area'
    else:
        _, cumulative = projected_arclength(family, p)
        span = float(cumulative[-1])
        nw, nt = max(1, math.ceil(w / spacing)), max(1, math.ceil(span / spacing))
        measure = 'parametric surface area counted with multiplicity: integral |dc/dt cross ez| dt du'
    if not math.isfinite(span) or span <= 0:
        raise ValueError('Scaffold span must be finite and positive.')
    copies = nw * nt
    strands = p.get('strand_count', 1)
    total = copies * strands
    if total > MAX_COPIES or (atom_count is not None and total * atom_count > MAX_ATOMS):
        raise ValueError('Build exceeds 50,000 copies or 2,000,000 atoms including all strands. Increase L or reduce dimensions/strands.')
    return dict(version=SAMPLING_VERSION, domain_measure=measure, area=w*span,
                nominal_area_budget=w*span/(spacing*spacing), width_cells=nw,
                longitudinal_cells=nt, width_cell_size=w/nw, longitudinal_cell_size=span/nt,
                copies_per_strand=copies, copy_count=total,
                atom_count=total*atom_count if atom_count is not None else None,
                placement='cell centres over the entire domain; no nearest-neighbour walk or truncation',
                spacing_definition='L is a sampling scale, not a Euclidean nearest-neighbour guarantee or collision threshold')


def spiral_points(name, p, chirality):
    family = family_of(name)
    plan = sampling_plan(name, p)
    nt, nw = plan['longitudinal_cells'], plan['width_cells']
    t_grid, cumulative = projected_arclength(family, p)
    targets = (np.arange(nt) + .5) * cumulative[-1] / nt
    t = np.interp(targets, cumulative, t_grid)
    r, _ = radial_profile(family, p, t)
    centre = np.column_stack((r*np.cos(chirality*t), r*np.sin(chirality*t), p['P']*t/(2*math.pi)))
    offsets = p['W'] * ((np.arange(nw)+.5)/nw-.5)
    points = np.tile(centre, (nw, 1))
    points[:, 2] += np.repeat(offsets, nt)
    return points
