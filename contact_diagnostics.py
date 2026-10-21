"""All-site inter-copy proximity screening, not an energetic clash score."""
import time
import numpy as np
from scipy.spatial import cKDTree


def diagnose_contacts(structures, cutoff, pair_work_limit=5000000, seconds_limit=15.0):
    start = time.perf_counter()
    blocks = np.asarray(structures, dtype=float)
    size = blocks.shape[1]
    xyz = blocks.reshape((-1, 3))
    result = dict(schema='helicraft-contacts-v1', cutoff_angstrom=float(cutoff),
                  definition='Unordered pairs of sites in DIFFERENT rigid template copies with Euclidean distance < cutoff. All sites including hydrogens are considered; no periodic images.',
                  interpretation='Geometric close-contact candidates only. No element/bead radii, force field or physical overlap criterion is inferred. L is unrelated to this threshold.',
                  total_sites=len(xyz), inspected_sites=0, pair_count=0,
                  coincident_pair_count=0, coincidence_tolerance_angstrom=1e-8,
                  minimum_reported_distance_angstrom=None, examples=[], complete=True)
    if cutoff == 0:
        result.update(complete=False, status='disabled', elapsed_seconds=0.)
        return result
    tree = cKDTree(xyz)
    work = 0
    for i, point in enumerate(xyz):
        neighbours = tree.query_ball_point(point, cutoff)
        work += len(neighbours)
        if work > pair_work_limit or time.perf_counter() - start > seconds_limit:
            result.update(complete=False, status='partial_resource_limit', limitation='Pair counts are lower bounds; unvisited sites were not cleared. Reduce the cutoff or use offline analysis.')
            break
        js = np.asarray([j for j in neighbours if j > i and j // size != i // size], dtype=int)
        if len(js):
            distances = np.linalg.norm(xyz[js] - point, axis=1)
            keep = distances < cutoff
            js, distances = js[keep], distances[keep]
            result['pair_count'] += len(js)
            result['coincident_pair_count'] += int(np.count_nonzero(distances < 1e-8))
            if len(js):
                smallest = float(distances.min())
                previous = result['minimum_reported_distance_angstrom']
                result['minimum_reported_distance_angstrom'] = smallest if previous is None else min(previous, smallest)
            for j, d in zip(js[:max(0, 64-len(result['examples']))], distances):
                result['examples'].append(dict(site_i=i+1, site_j=int(j)+1, copy_i=i//size+1, copy_j=int(j)//size+1, distance_angstrom=float(d)))
        result['inspected_sites'] = i+1
    if result['complete']: result['status'] = 'complete'
    result['elapsed_seconds'] = time.perf_counter() - start
    return result
