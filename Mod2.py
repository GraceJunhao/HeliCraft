from sampling import sampling_plan, spiral_points, family_of, FAMILIES
from Mod8 import generate_points_flat, generate_points_twist

def calculate_spiral_surface_area(spiral_type, params):
    return sampling_plan(spiral_type, params)['area']

def generate_grid_points_on_surface(spiral_type, params, chirality):
    family = family_of(spiral_type)
    plan = sampling_plan(spiral_type, params)
    if family not in FAMILIES[4:]:
        return spiral_points(spiral_type, params, chirality)
    args = (plan['copies_per_strand'], plan['width_cells'], plan['longitudinal_cells'], params)
    if family == 'Twist带': return generate_points_twist(*args, chirality=chirality)
    return generate_points_flat(*args)
