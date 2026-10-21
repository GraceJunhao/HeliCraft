import numpy as np
from cg_templates import get_template, match_template_to_symbols

def infer_box_from_structures(structure_list, margin=5.0):
    all_coords = np.vstack(structure_list)
    mins = all_coords.min(axis=0)
    maxs = all_coords.max(axis=0)
    center = 0.5 * (mins + maxs)
    shifted = [coords - center for coords in structure_list]
    box = (maxs - mins) + 2.0 * margin
    return shifted, box

def prepare_template(symbols, template_name="PLBB", strict=True):
    tpl = get_template(template_name)
    ok, tpl_symbols = match_template_to_symbols(symbols, template_name, strict=strict)
    if not ok:
        raise ValueError(f"CG 模板匹配失败")
    return tpl

def save_all_structures_mst(structure_list, symbols, filename, template_name="PLBB", strict_match=True, margin=5.0):
    if not structure_list: return
    tpl = prepare_template(symbols, template_name=template_name, strict=strict_match)
    
    local_symbols = tpl["symbols"]
    local_masses = tpl["masses"]
    local_bonds = tpl["bonds"]
    local_angles = tpl["angles"]
    n_local = len(local_symbols)

    shifted_structures, box = infer_box_from_structures(structure_list, margin=margin)
    positions, types, masses, molecules, bonds, angles = [], [], [], [], [], []

    atom_offset = 0
    for mol_id, coords in enumerate(shifted_structures):
        positions.extend(coords.tolist())
        types.extend(local_symbols)
        masses.extend(local_masses)
        molecules.extend([mol_id] * n_local)
        for btype, i, j in local_bonds:
            bonds.append((btype, atom_offset + i, atom_offset + j))
        for atype, i, j, k in local_angles:
            angles.append((atype, atom_offset + i, atom_offset + j, atom_offset + k))
        atom_offset += n_local

    with open(filename, "w", encoding="utf-8") as f:
        f.write("mst_version 1.0\nnum_particles\n")
        f.write(f"{len(positions)}\ntimestep\n0\ndimension\n3\nbox\n")
        f.write(f"{box[0]:.6f} {box[1]:.6f} {box[2]:.6f}\nposition\n")
        for x, y, z in positions: f.write(f"{x:.6f} {y:.6f} {z:.6f}\n")
        f.write("type\n")
        for t in types: f.write(f"{t}\n")
        f.write("mass\n")
        for m in masses: f.write(f"{m:.6f}\n")
        
        if bonds:
            f.write("bond\n")
            for btype, i, j in bonds: f.write(f"{btype} {i} {j}\n")
        if angles:
            f.write("angle\n")
            for atype, i, j, k in angles: f.write(f"{atype} {i} {j} {k}\n")
            
        f.write("molecule\n")
        for mol in molecules: f.write(f"{mol}\n")
        f.write("mst_end\n")

def save_all_structures_xml(structure_list, symbols, filename, template_name="PLBB", strict_match=True, margin=5.0):
    if not structure_list: return
    tpl = prepare_template(symbols, template_name=template_name, strict=strict_match)
    local_symbols, local_masses, local_bonds = tpl["symbols"], tpl["masses"], tpl["bonds"]
    n_local = len(local_symbols)

    shifted_structures, box = infer_box_from_structures(structure_list, margin=margin)
    positions, types, masses, bonds = [], [], [], []

    atom_offset = 0
    for coords in shifted_structures:
        positions.extend(coords.tolist())
        types.extend(local_symbols)
        masses.extend(local_masses)
        for btype, i, j in local_bonds:
            bonds.append((btype, atom_offset + i, atom_offset + j))
        atom_offset += n_local

    natoms = len(positions)
    with open(filename, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<galamost_xml version="1.3">\n')
        f.write(f'<configuration time_step="0" dimensions="3" natoms="{natoms}" >\n')
        f.write(f'<box lx=" {box[0]:.6f}" ly=" {box[1]:.6f}" lz=" {box[2]:.6f}"/>\n')
        f.write(f'<position num="{natoms}">\n')
        for x, y, z in positions: f.write(f'{x: .6f}\t{y: .6f}\t{z: .6f}\n')
        f.write('</position>\n')
        f.write(f'<type num="{natoms}">\n')
        for t in types: f.write(f'{t}\n')
        f.write('</type>\n')
        f.write(f'<mass num="{natoms}">\n')
        for m in masses: f.write(f'{m: .6f}\n')
        f.write('</mass>\n')
        
        if bonds:
            f.write(f'<bond num="{len(bonds)}">\n')
            for btype, i, j in bonds: f.write(f'{btype}\t{i}\t{j}\n')
            f.write('</bond>\n')
            
        f.write('</configuration>\n</galamost_xml>\n')