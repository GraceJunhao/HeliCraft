import logging
import json
import hashlib
import time
from pathlib import Path
from release_info import RELEASE
from validation_rules import validate_config
from sampling import sampling_plan
from contact_diagnostics import diagnose_contacts
import numpy as np
from config_models import SpiralConfig

from Mod1 import generate_spiral
from Mod2 import generate_grid_points_on_surface
from Mod3 import compute_xl
from Mod4 import read_xyz_content, compute_reference_frame
from Mod5 import transform_structure_with_full_orientation
from Mod6 import save_all_structures_xyz, save_all_structures_pdb, save_all_structures_cif, PDBFormatError
from Mod9 import save_all_structures_mst, save_all_structures_xml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CleanSpiralBuilder:
    def __init__(self, config: SpiralConfig):
        self.config = config
        self.params_dict = config.model_dump()
        self.spiral_type = config.spiral_type
        
        self.dj = None  
        self.tangent_vectors = self.normal_vectors = None   
        self.transformed_structures = []  
        self.atoms = self.symbols = self.q = self.ab_vector = None  

    def run(self):
        logging.info(f"--- 引擎启动: {self.spiral_type} ---")
        started = time.perf_counter()
        self.atoms, self.symbols = read_xyz_content(self.config.xyz_file_path)
        self.q, self.ab_vector = compute_reference_frame(self.atoms, self.config.a_idx, self.config.b_idx)
        
        validate_config(self.config, len(self.atoms))
        self.sampling_metadata = sampling_plan(self.spiral_type, self.params_dict, len(self.atoms))
        self.template_sha256 = hashlib.sha256(Path(self.config.xyz_file_path).read_bytes()).hexdigest()
        self.dj = generate_grid_points_on_surface(self.spiral_type, self.params_dict, self.config.chirality)
        self.tangent_vectors, self.normal_vectors = compute_xl(self.dj, self.spiral_type, self.params_dict)
        
        self._align_structures()
        self._replicate_strands()
        self.construction_seconds = time.perf_counter() - started
        self.contact_report = diagnose_contacts(self.transformed_structures, self.config.contact_cutoff)
        write_started = time.perf_counter()
        self._save_outputs()
        self.writing_seconds = time.perf_counter() - write_started
        return self.transformed_structures

    def _align_structures(self):
        """在这里应用罗德里格斯旋转公式，实现单体的任意角度插入"""
        self.transformed_structures = []
        
        # 将用户输入的角度转换为弧度
        theta = np.radians(self.config.insertion_angle)
        
        for point, normal, tangent in zip(self.dj, self.normal_vectors, self.tangent_vectors):
            
            # 若角度不为 0，让法向量绕着切线向量(tangent)旋转 theta 角度
            if theta != 0.0:
                # 因为 normal 和 tangent 相互垂直，公式简化为：
                # v_rot = v * cos(θ) + (k × v) * sin(θ)
                rotated_normal = normal * np.cos(theta) + np.cross(tangent, normal) * np.sin(theta)
                # 重新归一化防止浮点数精度丢失
                rotated_normal = rotated_normal / np.linalg.norm(rotated_normal)
            else:
                rotated_normal = normal

            new_coords = transform_structure_with_full_orientation(
                self.atoms, self.q, self.ab_vector, point, rotated_normal, tangent
            )
            self.transformed_structures.append(new_coords)

    def _replicate_strands(self):
        """Rotate the complete placed strand, preserving its molecular frames.

        A second frame alignment from A/B alone would choose a new roll for an
        asymmetric template. Rotating coordinates and local vectors together
        guarantees exact rotational copies and preserves molecular chirality.
        """
        count = self.config.strand_count
        self.copies_per_strand = len(self.transformed_structures)
        self.strand_angles_deg = [
            (self.config.strand_phase_deg + 360.0 * j / count) % 360.0
            for j in range(count)
        ]
        self.strand_ids = np.repeat(np.arange(count), self.copies_per_strand)
        if count == 1 and self.strand_angles_deg[0] == 0:
            return  # Preserve the original single-strand coordinates exactly.
        base = np.asarray(self.transformed_structures)
        points, tangents, normals = self.dj, self.tangent_vectors, self.normal_vectors
        coordinates, anchors, tangent_blocks, normal_blocks = [], [], [], []
        for angle in self.strand_angles_deg:
            theta = np.radians(angle)
            c, s = np.cos(theta), np.sin(theta)
            rotation = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
            if angle == 0:
                coordinates.extend(base)
                anchors.append(points)
                tangent_blocks.append(tangents)
                normal_blocks.append(normals)
            else:
                coordinates.extend(base @ rotation.T)
                anchors.append(points @ rotation.T)
                tangent_blocks.append(tangents @ rotation.T)
                normal_blocks.append(normals @ rotation.T)
        self.transformed_structures = coordinates
        self.dj = np.concatenate(anchors)
        self.tangent_vectors = np.concatenate(tangent_blocks)
        self.normal_vectors = np.concatenate(normal_blocks)

    def _save_outputs(self):
        prefix = self.config.output_prefix
        atoms_per_res = self.config.atoms_per_residue or len(self.atoms)
        chain_ids = [chr(65 + int(i)) for i in self.strand_ids]
        settings = {k: v for k, v in self.params_dict.items()
                    if k not in ('xyz_file_path', 'output_prefix')}
        self.assembly_metadata = {
            'schema': 'helicraft-build-v2',
            'release': RELEASE,
            'template_sha256': self.template_sha256,
            'sampling': self.sampling_metadata,
            'contacts': self.contact_report,
            'construction_seconds': self.construction_seconds,
            'parameters': settings,
            'atom_count': len(self.transformed_structures) * len(self.atoms),
            'atoms_per_monomer': len(self.atoms),
            'copies_per_strand': self.copies_per_strand,
            'copy_count': len(self.transformed_structures),
            'ordering': 'strand, monomer copy, template atom; ranges below are 1-based inclusive',
            'strands': [dict(strand=j + 1, chain_id=chr(65 + j), phase_deg=angle,
                             first_copy=j * self.copies_per_strand + 1,
                             last_copy=(j + 1) * self.copies_per_strand,
                             first_atom=j * self.copies_per_strand * len(self.atoms) + 1,
                             last_atom=(j + 1) * self.copies_per_strand * len(self.atoms))
                        for j, angle in enumerate(self.strand_angles_deg)],
            'note': 'Rigid geometric placement; strand IDs do not define covalent connectivity or physical stability.'
        }
        with open(f'{prefix}_all.json', 'w', encoding='utf-8') as stream:
            json.dump(self.assembly_metadata, stream, indent=2, ensure_ascii=False)
        
        save_all_structures_xyz(self.transformed_structures, self.symbols, f"{prefix}_all.xyz")
        save_all_structures_cif(self.transformed_structures, self.symbols, f"{prefix}_all.cif", self.config.res_name, atoms_per_res, chain_ids=chain_ids)
        self.pdb_unavailable_reason = None
        try:
            save_all_structures_pdb(self.transformed_structures, self.symbols, f"{prefix}_all.pdb", self.config.res_name, atoms_per_res, chain_ids=chain_ids)
        except PDBFormatError as exc:
            # An unsupported legacy format must not prevent a valid XYZ/mmCIF build.
            # Remove a stale PDB if a standalone run reused an earlier output prefix.
            from pathlib import Path
            pdb_path = Path(f"{prefix}_all.pdb")
            if pdb_path.exists():
                pdb_path.unlink()
            self.pdb_unavailable_reason = str(exc)
            logging.info("PDB unavailable: %s", exc)
        
        if self.config.save_cg:
            save_all_structures_mst(self.transformed_structures, self.symbols, f"{prefix}_all.mst", template_name=self.config.cg_template_name)
            save_all_structures_xml(self.transformed_structures, self.symbols, f"{prefix}_all.xml", template_name=self.config.cg_template_name)
