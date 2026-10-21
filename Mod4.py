"""Strict single-frame XYZ parsing for atoms and named CG beads."""
import re
import numpy as np
MAX_XYZ_BYTES = 32 * 1024 * 1024

def read_xyz_content(xyz_file_path):
    with open(xyz_file_path, 'rb') as stream:
        raw = stream.read(MAX_XYZ_BYTES + 1)
    if len(raw) > MAX_XYZ_BYTES: raise ValueError('Template exceeds 32 MiB.')
    try: lines = raw.decode('utf-8-sig').splitlines()
    except UnicodeError: raise ValueError('XYZ must use UTF-8 text.') from None
    if len(lines) < 2 or not re.fullmatch(r'[0-9]+', lines[0].strip()):
        raise ValueError('XYZ needs an integer site count and a comment line.')
    count = int(lines[0].strip())
    if not 2 <= count <= 1000000: raise ValueError('XYZ must contain 2 to 1,000,000 sites.')
    rows = [line.split() for line in lines[2:] if line.strip()]
    if len(rows) != count:
        raise ValueError('XYZ declared count does not match coordinate rows; supply exactly one frame.')
    symbols, atoms = [], []
    for i, row in enumerate(rows):
        if len(row) != 4 or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_+-]{0,15}', row[0]):
            raise ValueError('XYZ row %d must contain a site label and three coordinates.' % (i+1))
        try: coordinate = [float(v) for v in row[1:]]
        except ValueError: raise ValueError('Invalid XYZ coordinate at row %d.' % (i+1)) from None
        if not np.isfinite(coordinate).all() or np.max(np.abs(coordinate)) > 1e8:
            raise ValueError('XYZ coordinates must be finite and within +/-1e8 angstroms.')
        symbols.append(row[0]); atoms.append(coordinate)
    return np.asarray(atoms), symbols

def compute_reference_frame(atoms, a_idx, b_idx):
    xyz = np.asarray(atoms, dtype=float)
    if xyz.ndim != 2 or xyz.shape[1] != 3 or not np.isfinite(xyz).all():
        raise ValueError('Reference template coordinates are invalid.')
    if any(isinstance(i, bool) or not isinstance(i, (int, np.integer)) or not 0 <= i < len(xyz) for i in (a_idx,b_idx)):
        raise ValueError('Reference indices must be zero-based integers within the template.')
    axis = xyz[b_idx] - xyz[a_idx]
    if np.linalg.norm(axis) < 1e-8:
        raise ValueError('Reference atoms must define a nonzero axis (length >= 1e-8 angstrom).')
    return (xyz[a_idx]+xyz[b_idx])/2, axis
