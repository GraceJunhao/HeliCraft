# cg_templates.py
# -*- coding: utf-8 -*-

"""
粗粒化模板库

用途：
1. 定义线性 coarse-grained 单元的 bead 类型、质量、bond、angle
2. 导出 MST/XML 时复用这些模板
3. 以后更换新的线性粗粒化单元时，只改这里

约定：
- symbols: 单个粗粒化单元内部 bead 类型顺序
- masses: 对应 bead 质量
- bonds : (bond_type, i, j)
- angles: (angle_type, i, j, k)

说明：
- 当前先只考虑“线性”粗粒化单元
- 非线性/支化/环状以后再扩展
"""

CG_TEMPLATES = {
    "PLBB": {
        "description": "Default 4-bead linear template: P-L-B-B",
        "symbols": ["P", "L", "B", "B"],
        "masses": [2.0, 1.0, 1.0, 1.0],
        "bonds": [
            ("bPL", 0, 1),
            ("bLB", 1, 2),
            ("bBB", 2, 3),
        ],
        "angles": [
            ("aPLB", 0, 1, 2),
            ("aLBB", 1, 2, 3),
        ],
    },

    "PLBB-dimer": {
        "description": "Default 4-bead linear template: P-L-B-B",
        "symbols": ["P", "L", "B", "B", "P", "L", "B", "B"],
        "masses": [2.0, 1.0, 1.0, 1.0, 2.0, 1.0, 1.0, 1.0],
        "bonds": [
            ("bPL", 0, 1),
            ("bLB", 1, 2),
            ("bBB", 2, 3),
            ("bPL", 4, 5),
            ("bLB", 5, 6),
            ("bBB", 6, 7),
        ],
        "angles": [
            ("aPLB", 0, 1, 2),
            ("aLBB", 1, 2, 3),
            ("aPLB", 4, 5, 6),
            ("aLBB", 5, 6, 7),
        ],
    },

    # 下面给你几个示例模板，后面可以按这个格式继续加
    "ABCD": {
        "description": "Example 4-bead linear template: A-B-C-D",
        "symbols": ["A", "B", "C", "D"],
        "masses": [1.0, 1.0, 1.0, 1.0],
        "bonds": [
            ("bAB", 0, 1),
            ("bBC", 1, 2),
            ("bCD", 2, 3),
        ],
        "angles": [
            ("aABC", 0, 1, 2),
            ("aBCD", 1, 2, 3),
        ],
    },

    "PBBBB": {
        "description": "Example 5-bead linear template: P-B-B-B-B",
        "symbols": ["P", "B", "B", "B", "B"],
        "masses": [2.0, 1.0, 1.0, 1.0, 1.0],
        "bonds": [
            ("bP1", 0, 1),
            ("b12", 1, 2),
            ("b23", 2, 3),
            ("b34", 3, 4),
        ],
        "angles": [
            ("aP12", 0, 1, 2),
            ("a123", 1, 2, 3),
            ("a234", 2, 3, 4),
        ],
    },
}


def list_templates():
    """
    返回所有可用模板名称
    """
    return list(CG_TEMPLATES.keys())


def get_template(name="PLBB"):
    """
    获取模板并做基本检查
    """
    if name not in CG_TEMPLATES:
        available = ", ".join(list_templates())
        raise KeyError(f"Unknown CG template '{name}'. Available templates: {available}")

    tpl = CG_TEMPLATES[name]

    required_keys = ["symbols", "masses", "bonds", "angles"]
    for k in required_keys:
        if k not in tpl:
            raise KeyError(f"Template '{name}' missing required key: {k}")

    n = len(tpl["symbols"])
    if len(tpl["masses"]) != n:
        raise ValueError(f"Template '{name}': masses length != symbols length")

    # 检查 bond / angle 索引合法性
    for item in tpl["bonds"]:
        if len(item) != 3:
            raise ValueError(f"Template '{name}': invalid bond entry {item}")
        _, i, j = item
        if not (0 <= i < n and 0 <= j < n):
            raise ValueError(f"Template '{name}': bond index out of range {item}")

    for item in tpl["angles"]:
        if len(item) != 4:
            raise ValueError(f"Template '{name}': invalid angle entry {item}")
        _, i, j, k = item
        if not (0 <= i < n and 0 <= j < n and 0 <= k < n):
            raise ValueError(f"Template '{name}': angle index out of range {item}")

    return tpl


def pretty_print_template(name="PLBB"):
    tpl = get_template(name)
    print("=" * 60)
    print(f"Template name : {name}")
    print(f"Description   : {tpl.get('description', '')}")
    print(f"Symbols       : {tpl['symbols']}")
    print(f"Masses        : {tpl['masses']}")
    print(f"Bonds         : {tpl['bonds']}")
    print(f"Angles        : {tpl['angles']}")
    print("=" * 60)


def match_template_to_symbols(input_symbols, template_name="PLBB", strict=True):
    """
    检查当前 xyz 模板读入的 symbols 是否与 CG 模板一致

    strict=True:
        要求完全一致（顺序也一致）
    strict=False:
        只检查 bead 数是否一致
    """
    tpl = get_template(template_name)
    tpl_symbols = tpl["symbols"]

    if strict:
        ok = list(input_symbols) == list(tpl_symbols)
        return ok, tpl_symbols

    ok = len(input_symbols) == len(tpl_symbols)
    return ok, tpl_symbols