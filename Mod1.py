import numpy as np
from Mod8 import generate_flat, generate_twist

def get_helical_axis(spiral_type):
    if "Flat带" in spiral_type or "Twist带" in spiral_type:
        return np.array([0.0, 1.0, 0.0])
    return np.array([0.0, 0.0, 1.0])

def generate_spiral(spiral_type, params):
    phi = (1 + np.sqrt(5)) / 2
    # 直接读取我们刚才在 config 算好的精确手性
    chirality = params.get('chirality', 1)
    n_line = params.get("n_line", 1000)

    if "Flat带" in spiral_type: return generate_flat(params)
    elif "Twist带" in spiral_type: return generate_twist(params, chirality=chirality)

    N = params.get('N', 1.0)
    if N <= 0: N = 1.0  # 防弹衣 1
    
    t = np.linspace(0, N * 2 * np.pi, n_line)

    if '圆柱状螺旋' in spiral_type:
        R, P = params.get('R',0), params.get('P',0)
        z = t * P / (2 * np.pi)
        x = R * np.cos(chirality * t)
        y = R * np.sin(chirality * t)

    elif '锥形螺旋' in spiral_type:
        Rbase, Rtop = params.get('Rbase',0), params.get('Rtop',0)
        P = params.get('P', 0)
        safe_P = P if P != 0 else 0.001 # 防弹衣 2：防止除 0
        z = t * P / (2 * np.pi)
        R = Rbase + (Rtop - Rbase) * (z / (safe_P * N))
        x = R * np.cos(chirality * t)
        y = R * np.sin(chirality * t)

    elif '阿基米德螺旋' in spiral_type:
        Rbase, k = params.get('Rbase',0), params.get('k',0)
        P = params.get('P', 0)
        R = Rbase + k * t
        z = t * P / (2 * np.pi)
        x = R * np.cos(chirality * t)
        y = R * np.sin(chirality * t)

    elif '斐波那契' in spiral_type or '黄金螺旋' in spiral_type:
        Rbase, P = params.get('Rbase',0), params.get('P', 0)
        k_val = np.log(phi) / (2 * np.pi)
        R = Rbase * np.exp(k_val * t)
        z = t * P / (2 * np.pi)
        x = R * np.cos(chirality * t)
        y = R * np.sin(chirality * t)
    else:
        raise ValueError(f"未知的螺旋类型: {spiral_type}")

    z_upper = z + params.get('W', 20) / 2
    z_lower = z - params.get('W', 20) / 2

    return np.column_stack((x, y, z)), np.column_stack((x, y, z_upper)), np.column_stack((x, y, z_lower))