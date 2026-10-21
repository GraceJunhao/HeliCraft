import numpy as np
from scipy.spatial.transform import Rotation

def align_vector(source, target):
    """
    计算将源向量对齐到目标向量的旋转矩阵
    """
    source = source / np.linalg.norm(source)
    target = target / np.linalg.norm(target)
    
    if np.allclose(source, target):
        return np.eye(3)
    
    if np.allclose(source, -target):
        if abs(source[0]) < 0.9:
            axis = np.array([1, 0, 0])
        else:
            axis = np.array([0, 1, 0])
        axis = axis - np.dot(axis, source) * source
        axis = axis / np.linalg.norm(axis)
        return Rotation.from_rotvec(np.pi * axis).as_matrix()
    
    axis = np.cross(source, target)
    axis = axis / np.linalg.norm(axis)
    angle = np.arccos(np.clip(np.dot(source, target), -1.0, 1.0))
    return Rotation.from_rotvec(angle * axis).as_matrix()

def transform_structure_xyz(atoms, q, ab_vector, target_point, ribbon_normal, tangent_vector=None):
    """
    基于螺旋带法向量的结构变换
    """
    translated = atoms - q + target_point
    rotation_matrix = align_vector(ab_vector, ribbon_normal)
    rotated = np.dot(translated - target_point, rotation_matrix.T) + target_point
    return rotated

def transform_structure_with_full_orientation(atoms, q, ab_vector, target_point, ribbon_normal, tangent_vector, secondary_vector=None):
    """
    使用完整定向信息的结构变换
    """
    translated = atoms - q + target_point
    
    target_z = ribbon_normal / np.linalg.norm(ribbon_normal)
    target_x = tangent_vector / np.linalg.norm(tangent_vector)
    target_y = np.cross(target_z, target_x)
    target_y = target_y / np.linalg.norm(target_y)
    target_x = np.cross(target_y, target_z)
    target_rotation = np.column_stack([target_x, target_y, target_z])
    
    source_z = ab_vector / np.linalg.norm(ab_vector)
    if secondary_vector is not None:
        source_x = secondary_vector / np.linalg.norm(secondary_vector)
        source_x = source_x - np.dot(source_x, source_z) * source_z
        source_x = source_x / np.linalg.norm(source_x)
    else:
        if abs(source_z[0]) < 0.9:
            source_x = np.array([1, 0, 0])
        else:
            source_x = np.array([0, 1, 0])
        source_x = source_x - np.dot(source_x, source_z) * source_z
        source_x = source_x / np.linalg.norm(source_x)
    
    source_y = np.cross(source_z, source_x)
    source_rotation = np.column_stack([source_x, source_y, source_z])
    
    rotation_matrix = np.dot(target_rotation, source_rotation.T)
    rotated = np.dot(translated - target_point, rotation_matrix.T) + target_point
    
    return rotated

def validate_transformation(original_atoms, transformed_atoms, ab_vector, ribbon_normal, a, b, alignment_threshold=0.85):
    """
    验证变换是否保持了原子间距离并检查对齐质量
    """
    # 检查原子间距离
    n_atoms = len(original_atoms)
    for i in range(n_atoms):
        for j in range(i+1, n_atoms):
            orig_dist = np.linalg.norm(original_atoms[i] - original_atoms[j])
            trans_dist = np.linalg.norm(transformed_atoms[i] - transformed_atoms[j])
            if abs(orig_dist - trans_dist) > 1e-10:
                print(f"警告：原子 {i} 和 {j} 之间的距离发生变化：{orig_dist:.6f} -> {trans_dist:.6f}")
                return False
    
    # 检查 ab_vector 与 ribbon_normal 的对齐，使用正确的 a 和 b 索引
    transformed_ab_vector = transformed_atoms[b] - transformed_atoms[a]  # Use selected indices
    transformed_ab_vector = transformed_ab_vector / np.linalg.norm(transformed_ab_vector)
    ribbon_normal = ribbon_normal / np.linalg.norm(ribbon_normal)
    cos_angle = np.dot(transformed_ab_vector, ribbon_normal)
    if abs(cos_angle) < alignment_threshold:  # Use abs() to handle antiparallel cases (cos ~ -1)
        print(f"警告：变换后的 ab_vector 与法向量对齐度不足，余弦值 {cos_angle:.3f} < {alignment_threshold}")
        return False
    
    return True