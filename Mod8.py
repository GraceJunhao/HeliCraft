import numpy as np


def generate_flat(params):
    """
    生成 flat ribbon 的 center / upper / lower
    约定：
    - 长轴沿 y
    - 带宽方向沿 x
    - z = 0
    """
    length = params["Length"]
    W = params["W"]
    n_line = params.get("n_line", 1000)

    y = np.linspace(0.0, length, n_line)
    x = np.zeros_like(y)
    z = np.zeros_like(y)

    center = np.column_stack((x, y, z))
    upper = np.column_stack((np.full_like(y, +W / 2.0), y, z))
    lower = np.column_stack((np.full_like(y, -W / 2.0), y, z))
    return center, upper, lower


def generate_twist(params, chirality=1):
    """
    生成 twisted ribbon 的 center / upper / lower
    约定：
    - 中心线沿 y
    - 带宽方向绕 y 轴旋转
    - twist_turns 表示在总长度内完成多少整圈扭转
    - chirality=+1 遵循绕 +y 轴的右手定则
    """
    length = params["Length"]
    W = params["W"]
    twist_turns = params["twist_turns"]
    n_line = params.get("n_line", 1000)

    y = np.linspace(0.0, length, n_line)
    x0 = np.zeros_like(y)
    z0 = np.zeros_like(y)

    theta = chirality * 2.0 * np.pi * twist_turns * (y / length)

    center = np.column_stack((x0, y, z0))

    ex = np.cos(theta)
    ez = -np.sin(theta)

    upper = np.column_stack((+W / 2.0 * ex, y, +W / 2.0 * ez))
    lower = np.column_stack((-W / 2.0 * ex, y, -W / 2.0 * ez))
    return center, upper, lower


def generate_points_flat(num_structures, num_layers, points_per_layer, params):
    """
    flat 的网格点
    """
    offsets, y_vals = _ribbon_cell_centers(num_layers, points_per_layer, params)
    transverse, longitudinal = np.meshgrid(offsets, y_vals, indexing="ij")
    return np.column_stack((transverse.ravel(), longitudinal.ravel(), np.zeros(transverse.size)))


def generate_points_twist(num_structures, num_layers, points_per_layer, params, chirality=1):
    """
    twisted 的网格点
    """
    length = params["Length"]
    twist_turns = params["twist_turns"]
    offsets, y_vals = _ribbon_cell_centers(num_layers, points_per_layer, params)
    transverse, longitudinal = np.meshgrid(offsets, y_vals, indexing="ij")
    theta = chirality * 2.0 * np.pi * twist_turns * longitudinal / length
    return np.column_stack((
        (transverse * np.cos(theta)).ravel(),
        longitudinal.ravel(),
        (-transverse * np.sin(theta)).ravel(),
    ))


def _ribbon_cell_centers(num_layers, points_per_layer, params):
    """Complete, symmetric parameter grid with one anchor per sampling cell.

    The legacy generator signatures retain num_structures for compatibility,
    but never truncate this grid: all transverse layers cover the full length.
    L controls the integer counts; cell sizes adapt evenly to the given extent.
    """
    width = params["W"]
    length = params["Length"]
    n_width = max(1, int(num_layers))
    n_length = max(1, int(points_per_layer))
    offsets = width * ((np.arange(n_width) + 0.5) / n_width - 0.5)
    y_vals = length * (np.arange(n_length) + 0.5) / n_length
    return offsets, y_vals


def get_flat_width_direction(point, params):
    """
    flat 的宽度方向向量
    """
    return np.array([1.0, 0.0, 0.0])


def get_twist_width_direction(point, params, chirality=1):
    """
    twist 的宽度方向向量
    """
    length = params["Length"]
    twist_turns = params["twist_turns"]
    y = point[1]
    theta = chirality * 2.0 * np.pi * twist_turns * (y / length)
    vec = np.array([np.cos(theta), 0.0, -np.sin(theta)])
    return vec / np.linalg.norm(vec)
