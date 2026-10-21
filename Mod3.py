import numpy as np

def get_helical_axis(spiral_type):
    """获取整体的长轴方向"""
    if "Flat带" in spiral_type or "Twist带" in spiral_type:
        return np.array([0.0, 1.0, 0.0])
    return np.array([0.0, 0.0, 1.0])

def compute_xl(dj_points, spiral_type, params):
    """
    计算每个网格点的切线向量和法向量
    返回: (tangent_vectors, normal_vectors)
    """
    tangent_vectors = []
    normal_vectors = []
    chirality = params.get("chirality", 1)
    
    for point in dj_points:
        # 1. 采用微积分解析求导，获取完美的切线向量（不再依赖数组索引顺序）
        tangent = calculate_analytical_tangent(point, spiral_type, params, chirality)
        if np.linalg.norm(tangent) > 1e-10:
            tangent = tangent / np.linalg.norm(tangent)
        else:
            tangent = np.array([1.0, 0.0, 0.0])
            
        # 2. 计算法向量
        normal = calculate_normal_vector(point, tangent, spiral_type, params)
        
        tangent_vectors.append(tangent)
        normal_vectors.append(normal)
        
    return np.array(tangent_vectors), np.array(normal_vectors)

def calculate_analytical_tangent(point, spiral_type, params, chirality):
    """
    核心黑科技：通过当前坐标 (x,y,z) 的偏导数直接算出完美的切线方向
    """
    x, y, z = point
    P = params.get("P", 0.0)
    c = chirality
    
    if "Flat带" in spiral_type:
        return np.array([0.0, 1.0, 0.0])
        
    elif "Twist带" in spiral_type:
        Length = params.get("Length", 50.0)
        twist_turns = params.get("twist_turns", 1.0)
        # Twist 带沿 y 轴前进，横截面在 xz 平面扭转
        k_twist = c * 2.0 * np.pi * twist_turns / Length if Length != 0 else 0
        dx_dy = z * k_twist
        dz_dy = -x * k_twist
        return np.array([dx_dy, 1.0, dz_dy])

    else:
        # 所有螺旋结构通用微积分导数
        R_current = np.sqrt(x**2 + y**2)
        if R_current < 1e-6:
            R_current = 1e-6
            
        dR_dt = 0.0
        if "圆柱状螺旋" in spiral_type:
            dR_dt = 0.0
        elif "锥形螺旋" in spiral_type:
            Rbase = params.get("Rbase", 0.0)
            Rtop = params.get("Rtop", 0.0)
            N = params.get("N", 1.0)
            dR_dt = (Rtop - Rbase) / (2 * np.pi * N) if N != 0 else 0.0
        elif "阿基米德螺旋" in spiral_type:
            dR_dt = params.get("k", 0.0)
        elif "斐波那契" in spiral_type or "黄金" in spiral_type:
            k_val = np.log((1 + np.sqrt(5)) / 2) / (2 * np.pi)
            dR_dt = k_val * R_current

        # 链式求导：x = R*cos(ct), y = R*sin(ct)
        dx_dt = dR_dt * (x / R_current) - c * y
        dy_dt = dR_dt * (y / R_current) + c * x
        dz_dt = P / (2 * np.pi)
        
        return np.array([dx_dt, dy_dt, dz_dt])

def calculate_normal_vector(point, tangent, spiral_type, params):
    """
    计算螺旋带表面的法向量
    """
    helical_axis = get_helical_axis(spiral_type)

    if params.get("S_direction") == "parallel":
        return helical_axis

    if "Flat带" in spiral_type:
        return np.array([1.0, 0.0, 0.0])

    if "Twist带" in spiral_type:
        chirality = params.get("chirality", 1)
        Length = params.get("Length", 50.0)
        twist_turns = params.get("twist_turns", 1.0)
        y = point[1]
        theta = chirality * 2.0 * np.pi * twist_turns * (y / Length) if Length != 0 else 0
        vec = np.array([np.cos(theta), 0.0, -np.sin(theta)])
        return vec / np.linalg.norm(vec)

    if "圆柱状螺旋" in spiral_type:
        radial = np.array([point[0], point[1], 0.0])
        if np.linalg.norm(radial) > 1e-10:
            return radial / np.linalg.norm(radial)
        else:
            return np.array([1.0, 0.0, 0.0])

    # 锥形、阿基米德等：法向量 = 螺旋中心轴 × 切线向量
    normal = np.cross(helical_axis, tangent)
    if np.linalg.norm(normal) > 1e-10:
        return normal / np.linalg.norm(normal)
    else:
        return np.array([1.0, 0.0, 0.0])
