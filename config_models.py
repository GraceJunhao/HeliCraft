import math
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator
from typing import Optional

class SpiralConfig(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    contact_cutoff: float = Field(default=1.0, ge=0, le=100)
    spiral_type: str
    W: float
    L: float
    R: float = 0.0              
    P: float = 0.0              
    N: float = 1.0              
    Rbase: float = 0.0          
    Rtop: float = 0.0           
    k: float = 0.0              
    Length: float = 0.0         
    twist_turns: float = 0.0    
    # --- 新增：单体插入角度 ---
    insertion_angle: float = 0.0
    # Uniform, coaxial strands; N remains turns per strand.
    strand_count: StrictInt = Field(default=1, ge=1, le=12)
    strand_phase_deg: float = Field(default=0.0, ge=-360.0, le=360.0)
    # --------------------------
    xyz_file_path: str
    a_idx: StrictInt
    b_idx: StrictInt
    output_prefix: str = "web_output"
    res_name: str = "UNK"
    atoms_per_residue: Optional[int] = None
    chirality: int = 1
    save_cg: bool = False
    cg_template_name: str = "PLBB"

    @field_validator('W','L','R','P','N','Rbase','Rtop','k','Length','twist_turns',
                     'insertion_angle','strand_phase_deg','contact_cutoff',mode='before')
    @classmethod
    def reject_boolean_numbers(cls, value):
        if isinstance(value, bool): raise ValueError('Numeric parameters cannot be boolean.')
        return value

    @model_validator(mode='after')
    def parse_chirality(self):
        self.chirality = -1 if "左旋" in self.spiral_type else 1
        if not math.isfinite(self.strand_phase_deg):
            raise ValueError('Strand phase must be finite.')
        if 'Flat带' in self.spiral_type or 'Twist带' in self.spiral_type:
            if self.strand_count != 1 or self.strand_phase_deg != 0:
                raise ValueError('Coaxial strands are supported for the four spiral families only. Ribbons require one strand and phase 0.')
        elif self.strand_count > 1 or self.strand_phase_deg != 0:
            if not any(s in self.spiral_type for s in ('圆柱状螺旋', '锥形螺旋', '阿基米德螺旋', '斐波那契', '黄金')):
                raise ValueError('Unsupported scaffold for coaxial strands.')
        from validation_rules import validate_config
        validate_config(self)
        return self
