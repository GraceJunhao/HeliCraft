"""One parameter policy used by Jack, the web build and standalone construction."""
import math
from sampling import FAMILIES, family_of, sampling_plan

REQUIRED = dict(zip(FAMILIES, [('R','P','N'), ('Rbase','Rtop','P','N'),
    ('Rbase','k','P','N'), ('Rbase','P','N'), ('Length',), ('Length','twist_turns')]))
RULES_VERSION = 'parameters-v2'


def check_parameters(values, atom_count=None, require_template=True):
    issues, warnings = [], []
    family = values.get('base_type')
    if family not in FAMILIES:
        issues.append('Select a supported geometry.')
    fields = ['W', 'L', 'a_idx', 'b_idx', 'insertion_angle'] + list(REQUIRED.get(family, ()))
    for field in fields:
        value = values.get(field)
        if value is None:
            issues.append('Please provide %s.' % field)
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            issues.append('%s must be a finite number.' % field)
            continue
        if field in ('a_idx','b_idx'):
            if int(value) != value or value < 0 or (atom_count is not None and value >= atom_count):
                issues.append('%s must be a zero-based integer within the template.' % field)
        elif field == 'insertion_angle':
            if not 0 <= value <= 360: issues.append('Rotation must be between 0 and 360 degrees.')
        elif field in ('k','twist_turns'):
            if not 0 <= value <= (50 if field == 'twist_turns' else 10000):
                issues.append('%s is outside the supported nonnegative range.' % field)
        elif not 0 < value <= (50 if field == 'N' else 100000):
            issues.append('%s must be positive and within the supported range.' % field)
    m, phase = values.get('strand_count', 1), values.get('strand_phase_deg', 0)
    if isinstance(m, bool) or not isinstance(m, int) or not 1 <= m <= 12:
        issues.append('strand_count must be an integer from 1 to 12.')
    if isinstance(phase, bool) or not isinstance(phase, (int,float)) or not math.isfinite(phase) or not -360 <= phase <= 360:
        issues.append('strand_phase_deg must be finite and between -360 and 360.')
    if family in FAMILIES[4:] and (m != 1 or phase != 0):
        issues.append('Flat/Twisted ribbons require one strand and phase 0.')
    cutoff = values.get('contact_cutoff', 1.0)
    if isinstance(cutoff, bool) or not isinstance(cutoff, (int,float)) or not math.isfinite(cutoff) or not 0 <= cutoff <= 100:
        issues.append('contact_cutoff must be finite, from 0 to 100 angstroms; 0 disables screening.')
    if family != 'Flat带' and values.get('chirality') not in ('右旋','左旋'):
        issues.append('Select right- or left-handed winding.')
    if values.get('a_idx') is not None and values.get('a_idx') == values.get('b_idx'):
        issues.append('Reference atoms A and B must be different.')
    if require_template and (not isinstance(atom_count, int) or isinstance(atom_count, bool) or not 2 <= atom_count <= 1000000):
        issues.append('Upload a valid template containing 2 to 1,000,000 sites.')
    if not issues:
        try: sampling_plan(family, values, atom_count)
        except (ValueError, OverflowError) as error: issues.append(str(error))
    warnings.append('W is the global-z offset range [-W/2,+W/2] about spiral centrelines; for ribbons W is transverse width. L is not a collision threshold.')
    warnings.append('Build rechecks the uploaded coordinates and nonzero reference axis. Jack checks parameter data only; acceptance does not establish physical stability.')
    return issues, warnings


def config_values(config):
    values = config.model_dump() if hasattr(config, 'model_dump') else dict(config)
    values['base_type'] = family_of(values['spiral_type'])
    values['chirality'] = '左旋' if '左旋' in values['spiral_type'] else '右旋'
    return values


def validate_config(config, atom_count=None):
    issues, _ = check_parameters(config_values(config), atom_count, require_template=atom_count is not None)
    if issues: raise ValueError(' '.join(issues))
