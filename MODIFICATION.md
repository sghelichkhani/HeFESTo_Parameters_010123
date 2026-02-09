# Modifications to `generate_xml.py`

This document describes all changes made to `generate_xml.py` to produce a
complete, working `SLB24.xml` for the MMA-EoS framework. The original
script produced an XML with 18+ undefined phase references and no Landau
wrapping. The modified script generates a fully functional database with
15 solution phases, 13 standalone minerals, and 74 endmembers (34 of which
are Landau-wrapped).

---

## 1. Dynamic Endmember Discovery (was: hardcoded lists)

### Problem

The `phase_groups` dictionary hardcoded an `'endmembers'` key for each
solution phase, e.g.:

```python
'gt': {
    'name': 'Garnet',
    'endmembers': ['py', 'al', 'gr', 'mgmj'],  # only 4 of 7
    ...
}
```

These lists were incomplete. For example, the `phase/gt` file lists
7 endmembers (`py al gr mgmj namj andr knor`) but only 4 were hardcoded.
This caused 18+ endmembers to be silently dropped from the output.

### Fix

- **Removed** the `'endmembers'` key from every entry in `phase_groups`.
- **Changed** `add_phase_group()` to iterate over `phase_data.endmembers`
  (read from the first line of each `phase/{id}` file by the
  `PhaseInteraction` class) instead of `phase_info['endmembers']`.

The `phase_groups` dict now contains only metadata (`name`, `type`,
`allows_negative`, and optionally `solution_id`):

```python
'gt': {
    'name': 'Garnet',
    'type': 'EoS.Phases.RegularSolution, EoS.Core',
    'allows_negative': True,
},
```

### Files affected

- `generate_xml.py` lines 302-368 (`phase_groups` definition)
- `generate_xml.py` line 418 (`add_phase_group` endmember loop)

---

## 2. Added Missing Solution Phases

### Problem

Three solution phases present in the HeFESTo parameter files had no
corresponding entry in `phase_groups` and were completely absent from the
XML output.

### Fix

Added entries for:

| Phase ID | Name | Endmembers (from `phase/` file) | `allows_negative` |
|----------|------|---------------------------------|--------------------|
| `il` | Akimotoite | `mgil feil co hem esk` | `True` |
| `nal` | NAL Phase | `mnal fnal nnal` | `False` |
| `c2c` | HP-Clinopyroxene | `mgc2 fec2` | `False` |

Since `co` (corundum) is now an endmember of the `il` solution, it was
**removed** from the standalone list to avoid a duplicate id error.

### Spinel ID Collision

The phase directory name `sp` collides with the endmember mineral `sp`
(spinel). EoS XML ids must be unique. Following the SLB21 convention, the
spinel solution uses `solution_id: 'sps'`:

```python
'sp': {
    'name': 'Spinel',
    'type': 'EoS.Phases.RegularSolution, EoS.Core',
    'solution_id': 'sps',
},
```

`add_phase_group()` was updated to use
`phase_info.get('solution_id', phase_id)` when setting the XML id attribute.

---

## 3. Added Missing Standalone Minerals

### Problem

The standalone list only contained 7 minerals:
`['st', 'coes', 'qtz', 'capv', 'ky', 'neph', 'co']`

### Fix

Updated to 13 minerals (removed `co`, added 7 new ones):

```python
standalone = ['st', 'coes', 'qtz', 'capv', 'ky', 'neph',
              'fea', 'fee', 'feg', 'wo', 'pwo', 'apbo', 'lppv']
```

| ID | Name | Notes |
|----|------|-------|
| `fea` | alpha (bcc) Iron | Landau TC0 = 1043 K (Curie temp) |
| `fee` | epsilon (hcp) Iron | |
| `feg` | gamma (fcc) Iron | |
| `wo` | Wollastonite | |
| `pwo` | Pseudo-Wollastonite | |
| `apbo` | alpha-PbO2 SiO2 (seifertite) | |
| `lppv` | LS Fe2O3 Post-Perovskite | Landau TC0 = 10 K |

---

## 4. Rewrote `format_formula()`

### Problem

The original implementation used a simple regex:

```python
formula = re.sub(r'_(\d+)', r'\1', formula_raw)
pattern = r'([A-Z][a-z]?)(\d*\.?\d*)'
```

This cannot parse HeFESTo's site-mixed notation where parentheses denote
a crystallographic site with multiple elements, e.g.:
- `(Na_2Mg_1)Si_1Si_1Si_3O_12` (Na-majorite)
- `Na_1Mg_2(Al_5Si_1)O_12` (Mg-NAL phase)

These formulas were silently mangled, producing invalid XML.

### Fix

Replaced with a character-by-character tokenizer that handles two cases:

1. **Parenthesised site** `(...)`: collect content between `(` and `)`,
   parse element-count pairs within, strip underscores and drop counts of 1,
   then emit as a single `(...)` group. Read optional trailing count.

2. **Bare element** `El_N`: wrap in `()`, emit count if not 1.

Examples:

| HeFESTo input | Output |
|---------------|--------|
| `Mg_2Si_1O_4` | `(Mg)2(Si)(O)4` |
| `(Na_2Mg_1)Si_1Si_1Si_3O_12` | `(Na2Mg)(Si)(Si)(Si)3(O)12` |
| `Na_1Mg_2(Al_5Si_1)O_12` | `(Na)(Mg)2(Al5Si)(O)12` |
| `Fe_1` | `(Fe)` |

### Files affected

- `generate_xml.py` lines 161-226 (complete rewrite of `format_formula`)

---

## 5. Added Landau Modification Wrapping

### Problem

The `add_mineral_phase()` function always emitted a plain `DebyeSolid`
element, ignoring the Landau transition parameters (`T_crit`, `S_crit`,
`V_crit`) already parsed by `HeFESToParameter`. Iron-bearing phases
require Landau wrapping to account for magnetic ordering transitions;
without it, the magnetic entropy contribution to the free energy is missing
and iron partitioning predictions are systematically biased.

### Fix

`add_mineral_phase()` now checks `T_crit > 0`. When true, it emits a
nested structure matching the SLB21 convention (see `SLB21.xml` line 106,
hercynite):

```xml
<phase type="EoS.DebyeModel.LandauModification, EoS.DebyeModel" id="{id}">
  <blurb>{name}</blurb>
  <let name="TC0" unit="K">{T_crit}</let>
  <let name="SD" unit="J/mol/K">{S_crit}</let>
  <let name="VD" unit="m^3/mol">{V_crit}e-6</let>
  <phase type="EoS.DebyeModel.DebyeSolid, EoS.DebyeModel" id="{id}/nolandau">
    <blurb>{name} (no Landau)</blurb>
    <formula>...</formula>
    <!-- standard 10 DebyeSolid parameters -->
  </phase>
</phase>
```

When `T_crit == 0`, the plain `DebyeSolid` is emitted as before.

### Landau parameters

- `TC0` (K): critical temperature at zero pressure, from HeFESTo line 38
- `SD` (J/mol/K): maximum excess entropy, from HeFESTo line 39
- `VD` (m^3/mol): maximum excess volume, from HeFESTo line 40 (stored in
  cm^3/mol, converted by appending `e-6`)

34 endmembers have `T_crit > 0` and receive Landau wrapping in the output.
These range from low-T magnetic ordering (TC0 = 5 K for most Fe2+
endmembers) to high-T transitions well within mantle conditions (TC0 =
1043 K for alpha-iron, 950 K for hematite, 845.5 K for magnetite-structured
phases).

### Files affected

- `generate_xml.py` lines 434-514 (rewrite of `add_mineral_phase`)

---

## 6. Set `transparent-fallback` to `True`

### Problem

The global flag `transparent-fallback` was set to `False`. The EoS
`LandauModification` type computes an order parameter Q^2 = 1 - T/TC. When
T > TC (which is always true at mantle temperatures for phases with TC of
5-65 K), the Landau term is inapplicable and returns NaN. With
`transparent-fallback = False`, these NaN values propagate through all
property calculations.

### Fix

Changed to `True`, matching SLB21. When T > TC, the Landau wrapper now
falls back transparently to the underlying `DebyeSolid`.

### Files affected

- `generate_xml.py` line 295

---

## Summary of Output Changes

| Metric | Before | After |
|--------|--------|-------|
| Solution phases | 12 | 15 |
| Standalone minerals | 7 | 13 |
| Total endmembers | ~40 | 74 |
| Landau-wrapped | 0 | 34 |
| Undefined references | 18+ | 0 |
| `eos prop` on all phases | crashes | all OK |

## EoS Project Integration

After regenerating `SLB24.xml`, it must be:

1. Copied to `eos/EoS.DebyeModel/SLB24.xml`
2. Registered in `EoS.DebyeModel/EoS.DebyeModel.fsproj` as a `Content`
   item (this was also added):
   ```xml
   <Content Include="SLB24.xml">
     <CopyToOutputDirectory>PreserveNewest</CopyToOutputDirectory>
   </Content>
   ```
3. Republished: `dotnet publish -c Release ...`

## Verification

All 74 endmembers were tested with `eos prop -db=SLB24 {id} -P=10e9Pa
-T=1000K -o=V` and produce valid numerical output. No NaN, no crashes, no
undefined references.
