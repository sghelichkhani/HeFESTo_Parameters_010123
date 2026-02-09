# HeFESTo_Parameters_010123
Parameter set 010123 for use with the code:
HeFESTo by L. Stixrude and C. Lithgow-Bertelloni, 2005-
https://github.com/stixrude/HeFESToRepository

If you use this parameter set, please cite:

(1) Stixrude, L. and C. Lithgow-Bertelloni, Thermodynamics of mantle minerals - III. The role of iron, Geophysical Journal International, in press, 2024.

If you also use HeFESTo, please cite the following for the source of the HeFESTo code:

(2) Stixrude, L. and C. Lithgow-Bertelloni, Thermodynamics of mantle minerals - I. Physical properties, Geophysical Journal International, 162, 610-632, 2005.

(3) Stixrude, L. and C. Lithgow-Bertelloni, Thermodynamics of mantle minerals - II. Phase equilibria, Geophysical Journal International, 184, 1180-1213, 2011.

***** WARNING *****  

We grant the right to download and use this data, but do not grant the right to redistribute modified versions of the data in any form. If you have questions about the data, suggestions for improvements, or would like to ask for additional permissions or data files, please contact the authors:

Lars Stixrude: lstixrude@epss.ucla.edu
Carolina Lithgow-Bertelloni: clb@epss.ucla.edu

---

## XML Conversion for the MMA-EoS Framework

This is a fork of the HeFESTo parameter set that adds `generate_xml.py`, a
Python script to convert the native HeFESTo parameter files into an XML
database (`SLB24.xml`) compatible with the
[MMA-EoS library](https://chust.org/eos) by Thomas Chust. The MMA-EoS
framework expects mineral thermodynamic data in a specific XML schema
(`EoS.DebyeModel`) that differs from HeFESTo's plain-text format.
`generate_xml.py` bridges the two.

### Quick Start

```bash
python3 generate_xml.py
```

This reads every parameter file in the repository root and every interaction
file in `phase/`, then writes `SLB24.xml`. To use the output with MMA-EoS,
copy it into the EoS installation:

```
cp SLB24.xml  <eos-repo>/EoS.DebyeModel/SLB24.xml
```

and register it as a `Content` item in `EoS.DebyeModel.fsproj`:

```xml
<Content Include="SLB24.xml">
  <CopyToOutputDirectory>PreserveNewest</CopyToOutputDirectory>
</Content>
```

Then republish: `dotnet publish -c Release ...`

### What the Script Does

`generate_xml.py` performs three jobs:

1. **Parses individual mineral parameter files** (e.g. `fo`, `fa`, `mgpv`, ...)
   via the `HeFESToParameter` class. Each file contains 43 lines of
   thermodynamic properties. The class reads the chemical formula, mineral
   name, and all parameters (F0, V0, K0, K0', theta0, gamma0, q0, G0, G0',
   eta0, Landau critical temperature/entropy/volume, and others).

2. **Parses solution-phase interaction files** in `phase/` (e.g. `phase/ol`,
   `phase/cpx`, ...) via the `PhaseInteraction` class. Each file contains a
   header line of endmember names followed by a symmetric interaction-parameter
   matrix (W, in kJ/mol) and, after a `Volume` marker, a volume interaction
   matrix. The parser reads the upper-triangular portion of the energy matrix.

3. **Generates XML** matching the `EoS.DebyeModel` schema. The output
   structure mirrors the existing `SLB11.xml` (Stixrude & Lithgow-Bertelloni,
   2011) and `SLB21.xml` datasets already shipped with MMA-EoS.

### Unit Conversions

The HeFESTo files store quantities in "convenient" units. The XML requires SI:

| Parameter | HeFESTo unit | XML unit | Conversion |
|-----------|-------------|----------|------------|
| F0 | kJ/mol | J/mol | written as `{value}e3` |
| V0 | cm^3/mol | m^3/mol | written as `{value}e-6` |
| K0 | GPa | Pa | written as `{value}e9` |
| G0 | GPa | Pa | written as `{value}e9` |
| theta0, gamma0, q0, K0', G0', eta0 | dimensionless or K | same | no conversion |

### Script Structure

```
generate_xml.py
  |
  +-- HeFESToParameter       Parse one mineral file (43 parameters)
  +-- PhaseInteraction        Parse one phase/ file (endmembers + W matrix)
  +-- format_formula()        Convert HeFESTo formula notation to XML notation
  +-- create_xml_database()   Orchestrate reading, assembly, and XML output
  +-- add_phase_group()       Emit a RegularSolution phase with its endmembers
  +-- add_mineral_phase()     Emit a DebyeSolid (with optional Landau wrapper)
  +-- add_standalone_mineral()  Emit a mineral not belonging to any solution
  +-- add_let()               Helper to emit a <let name=... unit=...> element
```

### Key Design Decisions

#### Dynamic Endmember Discovery

Endmember lists are **not** hardcoded. The script reads the first line of each
`phase/{id}` file to discover which endmembers belong to each solution. The
`phase_groups` dictionary contains only metadata (display name, solution type,
whether negative components are allowed).

#### Formula Parsing

HeFESTo uses a notation with underscores for subscripts and parentheses for
crystallographic sites with mixed occupancy:

| HeFESTo | XML output |
|---------|------------|
| `Mg_2Si_1O_4` | `(Mg)2(Si)(O)4` |
| `(Na_2Mg_1)Si_1Si_1Si_3O_12` | `(Na2Mg)(Si)(Si)(Si)3(O)12` |
| `Na_1Mg_2(Al_5Si_1)O_12` | `(Na)(Mg)2(Al5Si)(O)12` |

`format_formula()` is a character-by-character tokenizer that handles both
simple element-count pairs and parenthesised mixed-site groups.

#### Landau Modification Wrapping

Many iron-bearing endmembers undergo magnetic ordering transitions described by
Landau theory. When the parsed critical temperature (T_crit, line 38) is
greater than zero, the script emits a nested XML structure:

```xml
<phase type="EoS.DebyeModel.LandauModification, EoS.DebyeModel" id="{id}">
  <let name="TC0" unit="K">{T_crit}</let>
  <let name="SD" unit="J/mol/K">{S_crit}</let>
  <let name="VD" unit="m^3/mol">{V_crit}e-6</let>
  <phase type="EoS.DebyeModel.DebyeSolid, EoS.DebyeModel" id="{id}/nolandau">
    <!-- standard 10 parameters -->
  </phase>
</phase>
```

When T_crit is zero a plain `DebyeSolid` is emitted instead. 34 of the 74
endmembers in the current parameter set have non-zero critical temperatures.

#### Spinel ID Collision

The phase directory name `sp` (spinel solution) collides with the endmember
mineral `sp` (spinel). Following the SLB11/SLB21 convention the solution is
assigned `id="sps"` via a `solution_id` override in the phase-groups
dictionary.

#### Transparent Fallback

The global flag `transparent-fallback` is set to `True`. This ensures that when
T > TC (which is the case at mantle temperatures for phases with TC of only a
few Kelvin), the Landau wrapper falls back transparently to the underlying
DebyeSolid rather than returning NaN.

### Output Summary

| Metric | Count |
|--------|-------|
| Solution phases | 15 |
| Standalone minerals | 13 |
| Total endmembers | 74 |
| Landau-wrapped endmembers | 34 |

Solution phases: olivine, orthopyroxene, clinopyroxene, garnet, perovskite,
post-perovskite, spinel, wadsleyite, ringwoodite, feldspar, Ca-ferrite,
ferropericlase, akimotoite, NAL phase, HP-clinopyroxene.

Standalone minerals: stishovite, coesite, quartz, Ca-perovskite, kyanite,
nepheline, alpha-iron, epsilon-iron, gamma-iron, wollastonite,
pseudo-wollastonite, seifertite (alpha-PbO2), LS-Fe2O3 post-perovskite.

### Verification

All 74 endmembers have been tested with:

```bash
eos prop -db=SLB24 {id} -P=10e9Pa -T=1000K -o=V
```

All produce valid numerical output with no NaN, no crashes, and no undefined
references.
