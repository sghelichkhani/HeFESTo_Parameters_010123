#!/usr/bin/env python3
"""
Generate XML file from HeFESTo parameter files
Similar structure to SLB11.xml but for the 010123 parameter set

Author: Sia Ghelichkhani
Date: 2026-02-09
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import xml.etree.ElementTree as ET
from xml.dom import minidom


class HeFESToParameter:
    """Class to store HeFESTo mineral parameters"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.mineral_id = Path(filepath).stem
        self.parameters = {}
        self.parse_file()

    def parse_file(self):
        """Parse a HeFESTo parameter file"""
        with open(self.filepath, 'r') as f:
            lines = f.readlines()

        # Parse the header line with formula and name
        if len(lines) > 0:
            parts = lines[0].strip().split()
            if len(parts) >= 2:
                self.formula_raw = parts[0]
                self.name = ' '.join(parts[1:])

        # Parse all numerical parameters
        param_map = {
            1: 'n_atoms',
            2: 'Z',
            3: 'mass',
            4: 'T0',
            5: 'F0',
            6: 'V0',
            7: 'K0',
            8: 'K0_p',
            9: 'K0K0_pp',
            10: 'theta0',
            11: 'debye_acoustic_2',
            12: 'debye_acoustic_3',
            13: 'sin_acoustic_1',
            14: 'sin_acoustic_2',
            15: 'sin_acoustic_3',
            16: 'einstein_1',
            17: 'weight_einstein_1',
            18: 'einstein_2',
            19: 'weight_einstein_2',
            20: 'einstein_3',
            21: 'weight_einstein_3',
            22: 'einstein_4',
            23: 'weight_einstein_4',
            24: 'optic_upper',
            25: 'optic_lower',
            26: 'gamma0',
            27: 'q0',
            28: 'beta',
            29: 'gammael0',
            30: 'q2A2',
            31: 'high_temp_approx',
            32: 'BM_or_Vinet',
            33: 'Einstein_or_Debye',
            34: 'zero_point_pressure',
            35: 'G0',
            36: 'G0_p',
            37: 'G0_T',
            38: 'T_crit',
            39: 'S_crit',
            40: 'V_crit',
            41: 'van_laar',
            42: 'C12_p',
            43: 'C44_p',
        }

        for i, line in enumerate(lines[1:], start=1):
            parts = line.strip().split()
            if parts and i in param_map:
                try:
                    value = float(parts[0])
                    self.parameters[param_map[i]] = value
                except (ValueError, IndexError):
                    pass

    def get_formula(self) -> str:
        """Convert HeFESTo formula to standard format"""
        # Parse formula like Mg_2Si_1O_4 to (Mg)2SiO4
        formula = self.formula_raw
        # Remove trailing underscores and clean up
        formula = re.sub(r'_(\d+)', r'\1', formula)
        # For simple cases, we'll need more sophisticated parsing
        # This is a placeholder
        return formula


class PhaseInteraction:
    """Class to store phase interaction parameters"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.phase_id = Path(filepath).stem
        self.endmembers = []
        self.interactions = []
        self.parse_file()

    def parse_file(self):
        """Parse a phase interaction file"""
        with open(self.filepath, 'r') as f:
            lines = f.readlines()

        if not lines:
            return

        # First line contains endmember names
        self.endmembers = lines[0].strip().split()

        # Find where "Volume" appears (separates energy from volume interactions)
        volume_line = -1
        for idx, line in enumerate(lines):
            if 'Volume' in line:
                volume_line = idx
                break

        # If no Volume marker, use all remaining lines
        if volume_line == -1:
            volume_line = len(lines)

        # Subsequent lines contain interaction parameters (W matrix)
        # Each row i (starting from line 1) contains interactions for endmember i
        # with all endmembers. We read upper triangular part (j > i) to avoid duplicates
        n = len(self.endmembers)
        for i in range(1, min(n + 1, volume_line)):
            if i < len(lines):
                values = lines[i].strip().split()
                # i-1 is the endmember index for this row (line 1 = endmember 0)
                row_idx = i - 1
                # Read columns to the right (j > row_idx) for upper triangular
                for j in range(row_idx + 1, min(n, len(values))):
                    try:
                        W = float(values[j])
                        if W != 0.0:
                            self.interactions.append((
                                self.endmembers[row_idx],
                                self.endmembers[j],
                                W
                            ))
                    except ValueError:
                        pass


def format_formula(formula_raw: str) -> str:
    """
    Convert HeFESTo formula format to standard chemical formula.

    Handles both simple and site-mixed formulas:
      Mg_2Si_1O_4           -> (Mg)2(Si)(O)4
      (Na_2Mg_1)Si_1Si_1Si_3O_12 -> (Na2Mg)(Si)(Si)(Si)3(O)12
      Na_1Mg_2(Al_5Si_1)O_12     -> (Na)(Mg)2(Al5Si)(O)12
      Fe_1                        -> (Fe)
    """
    formula = formula_raw.strip()
    result = []
    i = 0
    while i < len(formula):
        if formula[i] == '(':
            # Mixed site: collect until closing ')'
            i += 1
            site_content = []
            while i < len(formula) and formula[i] != ')':
                site_content.append(formula[i])
                i += 1
            if i < len(formula):
                i += 1  # skip ')'
            # Parse site content: remove underscores, drop counts of 1
            site_str = ''.join(site_content)
            # Process element_count pairs within site
            site_parsed = []
            for m in re.finditer(r'([A-Z][a-z]?)_?(\d*\.?\d*)', site_str):
                elem, count = m.group(1), m.group(2)
                if not elem:
                    continue
                if not count or count == '1':
                    site_parsed.append(elem)
                else:
                    site_parsed.append(f'{elem}{count}')
            result.append(f'({"".join(site_parsed)})')
            # Check for a count after the closing paren
            count_match = re.match(r'_?(\d+\.?\d*)', formula[i:])
            if count_match:
                count_val = count_match.group(1)
                if count_val != '1':
                    result.append(count_val)
                i += count_match.end()
        elif formula[i].isupper():
            # Single-element site
            elem = formula[i]
            i += 1
            if i < len(formula) and formula[i].islower():
                elem += formula[i]
                i += 1
            # Skip underscore before count
            if i < len(formula) and formula[i] == '_':
                i += 1
            # Read count
            count_match = re.match(r'(\d+\.?\d*)', formula[i:])
            count_val = ''
            if count_match:
                count_val = count_match.group(1)
                i += count_match.end()
            result.append(f'({elem})')
            if count_val and count_val != '1':
                result.append(count_val)
        else:
            i += 1  # skip unexpected characters

    return ''.join(result)


def create_xml_database(param_dir: str, phase_dir: str, output_file: str,
                        dataset_id: str = "SLB24",
                        dataset_name: str = "HeFESTo Parameters 010123"):
    """
    Generate XML database from HeFESTo parameters

    Args:
        param_dir: Directory containing individual mineral parameter files
        phase_dir: Directory containing phase interaction files
        output_file: Output XML file path
        dataset_id: ID for the dataset
        dataset_name: Name/description of dataset
    """

    # Read all mineral parameters
    minerals = {}
    for file in os.listdir(param_dir):
        filepath = os.path.join(param_dir, file)
        if os.path.isfile(filepath) and file not in ['changelog', 'README.md',
                                                       'out', '.gitignore']:
            try:
                param = HeFESToParameter(filepath)
                minerals[param.mineral_id] = param
            except Exception as e:
                print(f"Warning: Could not parse {file}: {e}")

    # Read phase interactions
    phases = {}
    if os.path.exists(phase_dir):
        for file in os.listdir(phase_dir):
            filepath = os.path.join(phase_dir, file)
            if os.path.isfile(filepath):
                try:
                    phase = PhaseInteraction(filepath)
                    if phase.endmembers:  # Only if it has content
                        phases[phase.phase_id] = phase
                except Exception as e:
                    print(f"Warning: Could not parse phase {file}: {e}")

    # Create XML structure
    root = ET.Element('module')
    root.set('xmlns', 'http://chust.org/eos')
    root.set('id', dataset_id)

    # Add blurb
    blurb = ET.SubElement(root, 'blurb')
    blurb.text = f"""
    Thermodynamic dataset: {dataset_name}
    Parameter set 010123 for use with HeFESTo

    Reference:
    Stixrude, L. and C. Lithgow-Bertelloni,
    Thermodynamics of mantle minerals - III. The role of iron,
    Geophysical Journal International, in press, 2024.
  """

    # Add reference temperature
    let_T0 = ET.SubElement(root, 'let')
    let_T0.set('name', 'T0')
    let_T0.set('unit', 'K')
    let_T0.text = '300.0'

    # Add configuration flags
    flags = [
        ('allows-negative-components', 'False'),
        ('excludes-endmember-configuration-entropy', 'False'),
        ('transparent-fallback', 'True'),
    ]
    for name, value in flags:
        let_flag = ET.SubElement(root, 'let')
        let_flag.set('name', name)
        let_flag.text = value

    # Define phase groupings — endmembers are read from phase files, not hardcoded
    phase_groups = {
        'ol': {
            'name': 'Olivine',
            'type': 'EoS.Phases.RegularSolution, EoS.Core',
        },
        'opx': {
            'name': 'Orthopyroxene',
            'type': 'EoS.Phases.RegularSolution, EoS.Core',
            'allows_negative': True,
        },
        'cpx': {
            'name': 'Clinopyroxene',
            'type': 'EoS.Phases.RegularSolution, EoS.Core',
            'allows_negative': True,
        },
        'gt': {
            'name': 'Garnet',
            'type': 'EoS.Phases.RegularSolution, EoS.Core',
            'allows_negative': True,
        },
        'pv': {
            'name': 'Perovskite',
            'type': 'EoS.Phases.RegularSolution, EoS.Core',
        },
        'ppv': {
            'name': 'Post-Perovskite',
            'type': 'EoS.Phases.RegularSolution, EoS.Core',
        },
        'sp': {
            'name': 'Spinel',
            'type': 'EoS.Phases.RegularSolution, EoS.Core',
            'solution_id': 'sps',  # avoid clash with endmember 'sp'
        },
        'wa': {
            'name': 'Wadsleyite',
            'type': 'EoS.Phases.RegularSolution, EoS.Core',
        },
        'ri': {
            'name': 'Ringwoodite',
            'type': 'EoS.Phases.RegularSolution, EoS.Core',
        },
        'plg': {
            'name': 'Feldspar',
            'type': 'EoS.Phases.RegularSolution, EoS.Core',
        },
        'cf': {
            'name': 'Ca-Ferrite',
            'type': 'EoS.Phases.RegularSolution, EoS.Core',
        },
        'mw': {
            'name': 'Ferropericlase',
            'type': 'EoS.Phases.RegularSolution, EoS.Core',
        },
        'il': {
            'name': 'Akimotoite',
            'type': 'EoS.Phases.RegularSolution, EoS.Core',
            'allows_negative': True,
        },
        'nal': {
            'name': 'NAL Phase',
            'type': 'EoS.Phases.RegularSolution, EoS.Core',
        },
        'c2c': {
            'name': 'HP-Clinopyroxene',
            'type': 'EoS.Phases.RegularSolution, EoS.Core',
        },
    }

    # Add phase groups
    for phase_id, phase_info in phase_groups.items():
        if phase_id in phases:
            add_phase_group(root, phase_id, phase_info, phases[phase_id], minerals)

    # Add standalone minerals
    standalone = ['st', 'coes', 'qtz', 'capv', 'ky', 'neph',
                  'fea', 'fee', 'feg', 'wo', 'pwo', 'apbo', 'lppv']
    for mineral_id in standalone:
        if mineral_id in minerals:
            add_standalone_mineral(root, mineral_id, minerals[mineral_id])

    # Pretty print XML
    xml_string = ET.tostring(root, encoding='unicode')
    dom = minidom.parseString(xml_string)
    pretty_xml = dom.toprettyxml(indent='  ')

    # Remove empty lines
    pretty_xml = '\n'.join([line for line in pretty_xml.split('\n')
                            if line.strip()])

    # Write to file
    with open(output_file, 'w') as f:
        f.write(pretty_xml)

    print(f"Generated XML file: {output_file}")
    print(f"Total minerals: {len(minerals)}")
    print(f"Phase groups: {len([p for p in phases.values() if p.endmembers])}")


def add_phase_group(root, phase_id, phase_info, phase_data, minerals):
    """Add a solution phase with multiple endmembers"""

    phase_elem = ET.SubElement(root, 'phase')
    phase_elem.set('type', phase_info['type'])
    phase_elem.set('id', phase_info.get('solution_id', phase_id))

    # Add blurb
    blurb = ET.SubElement(phase_elem, 'blurb')
    blurb.text = phase_info['name']

    # Add allows-negative-components if needed
    if phase_info.get('allows_negative', False):
        let_neg = ET.SubElement(phase_elem, 'let')
        let_neg.set('name', 'allows-negative-components')
        let_neg.text = 'True'

    # Add each endmember (read from phase interaction file)
    for endmember_id in phase_data.endmembers:
        if endmember_id in minerals:
            add_mineral_phase(phase_elem, endmember_id, minerals[endmember_id])

    # Add interactions from phase file
    for em1, em2, W in phase_data.interactions:
        interaction = ET.SubElement(phase_elem, 'interaction')
        interaction.set('unit', 'J/mol')
        interaction.set('value', f'{W:.1f}e3')  # Assuming W is in kJ/mol

        phase1 = ET.SubElement(interaction, 'phase')
        phase1.set('ref', em1)
        phase2 = ET.SubElement(interaction, 'phase')
        phase2.set('ref', em2)


def add_mineral_phase(parent, mineral_id, mineral):
    """Add a single mineral phase element, with Landau wrapping if needed"""

    params = mineral.parameters
    T_crit = params.get('T_crit', 0.0)
    S_crit = params.get('S_crit', 0.0)
    V_crit = params.get('V_crit', 0.0)
    needs_landau = T_crit > 0.0

    if needs_landau:
        # Outer Landau wrapper
        landau_phase = ET.SubElement(parent, 'phase')
        landau_phase.set('type', 'EoS.DebyeModel.LandauModification, EoS.DebyeModel')
        landau_phase.set('id', mineral_id)

        blurb_outer = ET.SubElement(landau_phase, 'blurb')
        blurb_outer.text = getattr(mineral, 'name', mineral_id.capitalize())

        add_let(landau_phase, 'TC0', 'K', f"{T_crit:.5f}")
        add_let(landau_phase, 'SD', 'J/mol/K', f"{S_crit:.3f}")
        add_let(landau_phase, 'VD', 'm^3/mol', f"{V_crit:.3f}e-6")

        # Inner DebyeSolid
        phase = ET.SubElement(landau_phase, 'phase')
        phase.set('type', 'EoS.DebyeModel.DebyeSolid, EoS.DebyeModel')
        phase.set('id', f'{mineral_id}/nolandau')

        blurb_inner = ET.SubElement(phase, 'blurb')
        blurb_inner.text = getattr(mineral, 'name', mineral_id.capitalize()) + ' (no Landau)'
    else:
        phase = ET.SubElement(parent, 'phase')
        phase.set('type', 'EoS.DebyeModel.DebyeSolid, EoS.DebyeModel')
        phase.set('id', mineral_id)

        blurb = ET.SubElement(phase, 'blurb')
        blurb.text = getattr(mineral, 'name', mineral_id.capitalize())

    # Formula
    formula = ET.SubElement(phase, 'formula')
    formula.text = format_formula(mineral.formula_raw)

    # F0 (kJ/mol to J/mol)
    if 'F0' in params:
        add_let(phase, 'F0', 'J/mol', f"{params['F0']:.3f}e3")

    # V0 (cm^3/mol to m^3/mol)
    if 'V0' in params:
        add_let(phase, 'V0', 'm^3/mol', f"{params['V0']:.4f}e-6")

    # K0 (GPa to Pa)
    if 'K0' in params:
        add_let(phase, 'K0', 'Pa', f"{params['K0']:.5f}e9")

    # K0_p (dimensionless)
    if 'K0_p' in params:
        add_let(phase, 'K0_p', '1', f"{params['K0_p']:.5f}")

    # theta0 (K)
    if 'theta0' in params:
        add_let(phase, 'θ0', 'K', f"{params['theta0']:.4f}")

    # gamma0 (dimensionless)
    if 'gamma0' in params:
        add_let(phase, 'γ0', '1', f"{params['gamma0']:.5f}")

    # q0 (dimensionless)
    if 'q0' in params:
        add_let(phase, 'q0', '1', f"{params['q0']:.5f}")

    # G0 (GPa to Pa)
    if 'G0' in params:
        add_let(phase, 'G0', 'Pa', f"{params['G0']:.1f}e9")

    # G0_p (dimensionless)
    if 'G0_p' in params:
        add_let(phase, 'G0_p', '1', f"{params['G0_p']:.5f}")

    # η0 (dimensionless) - derived from G0_T
    if 'G0_T' in params:
        add_let(phase, 'η0', '1', f"{params['G0_T']:.5f}")


def add_standalone_mineral(root, mineral_id, mineral):
    """Add a standalone mineral (not part of a solution)"""
    add_mineral_phase(root, mineral_id, mineral)


def add_let(parent, name, unit, value):
    """Add a <let> element with name, unit, and value"""
    let_elem = ET.SubElement(parent, 'let')
    let_elem.set('name', name)
    let_elem.set('unit', unit)
    let_elem.text = str(value)


if __name__ == '__main__':
    # Set paths
    param_dir = '/Users/sghelichkhani/Workplace/HeFESTo_Parameters_010123'
    phase_dir = '/Users/sghelichkhani/Workplace/HeFESTo_Parameters_010123/phase'
    output_file = '/Users/sghelichkhani/Workplace/HeFESTo_Parameters_010123/SLB24.xml'

    # Generate XML
    create_xml_database(
        param_dir=param_dir,
        phase_dir=phase_dir,
        output_file=output_file,
        dataset_id='SLB24',
        dataset_name='Stixrude & Lithgow-Bertelloni 2024 - The role of iron'
    )
