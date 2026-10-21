"""Coordinate writers with explicit legacy-PDB format limits."""
import math
import re


class PDBFormatError(ValueError):
    """Coordinates cannot be represented faithfully in a legacy PDB file."""


def _validate_structure(structure_list, symbols, res_name, atoms_per_residue):
    if not symbols:
        raise ValueError('At least one atom symbol is required.')
    if not isinstance(atoms_per_residue, int) or atoms_per_residue < 1:
        raise ValueError('atoms_per_residue must be a positive integer.')
    if not re.fullmatch(r'[A-Za-z0-9_]+', res_name):
        raise ValueError('Residue names must contain letters, digits or underscores.')
    if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', s) for s in symbols):
        raise ValueError('Invalid atom symbol.')
    for atoms in structure_list:
        for atom in atoms:
            if len(atom) != 3 or any(not math.isfinite(float(v)) for v in atom):
                raise ValueError('Coordinates must be finite x, y, z values.')


def _validate_pdb(structure_list, symbols, res_name, atoms_per_residue, combined=True):
    _validate_structure(structure_list, symbols, res_name, atoms_per_residue)
    counts = [len(atoms) for atoms in structure_list]
    count = sum(counts) if combined else max(counts, default=0)
    if count > 99999:
        raise PDBFormatError(f'PDB supports at most 99,999 atoms per model; this assembly has {count:,}. Use mmCIF or XYZ.')
    if (count + atoms_per_residue - 1) // atoms_per_residue > 9999:
        raise PDBFormatError('The residue count exceeds the PDB field limit. Use mmCIF or XYZ.')
    if len(res_name) > 3 or any(len(s) > 2 for s in symbols):
        raise PDBFormatError('Atom or residue labels exceed the PDB field limits. Use mmCIF or XYZ.')
    if not combined and len(structure_list) > 9999:
        raise PDBFormatError('The model count exceeds the PDB field limit. Use mmCIF or XYZ.')
    for atoms in structure_list:
        for atom in atoms:
            # Check after rounding: 9999.9996 would become 10000.000.
            if any(len(f'{float(v):8.3f}') != 8 for v in atom):
                raise PDBFormatError('Coordinates exceed the PDB fixed-column range. Use mmCIF or XYZ.')


def _atom_line(atom_id, symbol, res_name, res_id, atom, chain_id="A"):
    x, y, z = atom
    return (f'ATOM  {atom_id:5d} {symbol.ljust(4)} {res_name:3s} {chain_id}{res_id:4d}    '
            f'{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {symbol.rjust(2)}\n')


def save_combined_pdb(structure_list, symbols, filename, res_name, atoms_per_residue):
    _validate_pdb(structure_list, symbols, res_name, atoms_per_residue, combined=False)
    with open(filename, 'w') as f:
        for model_id, atoms in enumerate(structure_list, start=1):
            f.write(f'MODEL     {model_id:4d}\n')
            for j, atom in enumerate(atoms):
                f.write(_atom_line(j + 1, symbols[j % len(symbols)], res_name,
                                   j // atoms_per_residue + 1, atom))
            f.write('ENDMDL\n')
        f.write('END\n')


def _chain_ids(structure_list, chain_ids):
    if chain_ids is None:
        return ['A'] * len(structure_list)
    if len(chain_ids) != len(structure_list) or any(not re.fullmatch(r'[A-Z]', c) for c in chain_ids):
        raise ValueError('One uppercase chain identifier per molecular copy is required.')
    return chain_ids


def save_all_structures_pdb(structure_list, symbols, filename, res_name, atoms_per_residue, chain_ids=None):
    # Validate every record before opening/truncating a destination file.
    _validate_pdb(structure_list, symbols, res_name, atoms_per_residue)
    chains = _chain_ids(structure_list, chain_ids)
    with open(filename, 'w') as f:
        atom_id = 1
        for copy_index, atoms in enumerate(structure_list):
            for j, atom in enumerate(atoms):
                f.write(_atom_line(atom_id, symbols[j % len(symbols)], res_name,
                                   (atom_id - 1) // atoms_per_residue + 1, atom, chains[copy_index]))
                atom_id += 1
        f.write('END\n')


def save_all_structures_cif(structure_list, symbols, filename, res_name, atoms_per_residue, chain_ids=None):
    """Write one PDBx/mmCIF assembly with full IDs and XYZ precision.

    No unit cell, chemical bond orders or molecular topology are invented.
    Each rigid copy has its own label_asym_id; auth_seq_id retains grouping.
    """
    _validate_structure(structure_list, symbols, res_name, atoms_per_residue)
    chains = _chain_ids(structure_list, chain_ids)
    columns = ('group_PDB id type_symbol label_atom_id label_alt_id label_comp_id '
               'label_asym_id label_entity_id label_seq_id pdbx_PDB_ins_code '
               'Cartn_x Cartn_y Cartn_z occupancy B_iso_or_equiv auth_seq_id '
               'auth_comp_id auth_asym_id auth_atom_id pdbx_PDB_model_num').split()
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('data_HeliCraft\n#\n# Geometric assembly coordinates; no force-field topology assigned.\nloop_\n')
        f.write(''.join('_atom_site.' + name + '\n' for name in columns))
        atom_id = 1
        for copy_id, atoms in enumerate(structure_list, start=1):
            for j, (x, y, z) in enumerate(atoms):
                symbol = symbols[j % len(symbols)]
                name = f'{symbol}{j + 1}'
                residue = (atom_id - 1) // atoms_per_residue + 1
                f.write(f'HETATM {atom_id} {symbol} {name} . {res_name} M{copy_id} 1 . ? '
                        f'{x:.6f} {y:.6f} {z:.6f} 1.00 0.00 {residue} {res_name} {chains[copy_id - 1]} {name} 1\n')
                atom_id += 1
        f.write('#\n')


def save_combined_xyz(structure_list, symbols, filename):
    with open(filename, 'w') as f:
        for i, atoms in enumerate(structure_list):
            f.write(f'{len(atoms)}\nStructure {i + 1}\n')
            for j, atom in enumerate(atoms):
                symbol = symbols[j % len(symbols)]
                f.write(f'{symbol} {atom[0]:.6f} {atom[1]:.6f} {atom[2]:.6f}\n')


def save_all_structures_xyz(structure_list, symbols, filename):
    with open(filename, 'w') as f:
        if not structure_list:
            return
        total_atoms = sum(len(atoms) for atoms in structure_list)
        f.write(f'{total_atoms}\nCombined assembly structure\n')
        for atoms in structure_list:
            for j, atom in enumerate(atoms):
                symbol = symbols[j % len(symbols)]
                f.write(f'{symbol} {atom[0]:.6f} {atom[1]:.6f} {atom[2]:.6f}\n')
