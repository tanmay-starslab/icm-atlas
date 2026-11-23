# Intracluster Medium (ICM) & Galaxy Cluster Atlas (`icm.tanmaysingh.uk`)

**Interactive 3D Multi-Simulation Intracluster Medium (ICM) & Galaxy Cluster Atlas (352 TNG-Cluster Halos + 10 SIMBA-100 Massive Clusters + 20 TNG300-1 Clusters) + 12-Ion Voigt Absorption Sightline Explorer**

Live Portal: **[https://icm.tanmaysingh.uk](https://icm.tanmaysingh.uk)**

---

## Cosmic Hierarchy Sibling Portals

| Scale | Portal | Domain | Repository | Physical Span |
| :--- | :--- | :--- | :--- | :--- |
| **ISM** | Multiphase Interstellar Medium & Mixing Layers | **[ism.tanmaysingh.uk](https://ism.tanmaysingh.uk)** | [`tanmay-starslab/multiphase-ism`](https://github.com/tanmay-starslab/multiphase-ism) | $2500\text{ AU} \to 1\text{ kpc}$ |
| **CGM** | Circumgalactic Medium & Galactic Halos | **[galaxies.tanmaysingh.uk](https://galaxies.tanmaysingh.uk)** | [`tanmay-starslab/cgm-atlas`](https://github.com/tanmay-starslab/cgm-atlas) | $1\text{ kpc} \to 400\text{ kpc}$ |
| **ICM** | **Intracluster Medium & Massive Galaxy Clusters** | **[icm.tanmaysingh.uk](https://icm.tanmaysingh.uk)** | [`tanmay-starslab/icm-atlas`](https://github.com/tanmay-starslab/icm-atlas) | **$\pm 15\text{ kpc} \to \pm 4\text{ Mpc}$** |
| **IGM** | Intergalactic Medium & Whole-Box Cosmic Web | **[igm.tanmaysingh.uk](https://igm.tanmaysingh.uk)** | [`tanmay-starslab/igm-atlas`](https://github.com/tanmay-starslab/igm-atlas) | $35\text{ Mpc} \to 303\text{ Mpc}$ |

---

## Multi-Simulation Galaxy Cluster Sample ($z = 0$)

The **ICM & Galaxy Cluster Atlas** spans **382 massive galaxy clusters and rich groups** across three flagship cosmological hydrodynamic simulations:

1. **`TNG-Cluster` (All 352 $z=0$ Massive Galaxy Clusters, $M_{200c} = 10^{14.0}\text{--}10^{15.4}\,M_\odot$, Nelson et al. 2024)**
   - Dedicated zoom-in simulations of 352 massive galaxy clusters drawn from a $1\text{ Gpc}^3$ parent volume (`tngc_h14258311` through `tngc_h19514044`).
   - Full 5-level ($256^3$) 3D ICM octree cubes + 120-ray 12-ion Voigt absorption sightline libraries hosted on Hugging Face.
2. **`SIMBA-100 Clusters` (Top 10 $z=0$ Massive Galaxy Clusters, $\pm 4\text{ Mpc}$, Davé et al. 2019)**
   - All 10 most massive galaxy clusters from the $100\,h^{-1}\text{ Mpc}$ `SIMBA m100n1024` volume (`simba100_c01_h0` through `simba100_c10_h12`), capturing two-mode AGN jet + radiative feedback across cluster outskirts and cool cores.
3. **`TNG300-1 Clusters & Rich Groups` (20 $z=0$ Halos, Nelson et al. 2019a)**
   - Massive clusters and rich groups from the $302.6\text{ Mpc}$ `TNG300-1` cosmological volume (`tng300_sub0` through `tng300_sub623367`).

---

## 5-Level 3D ICM Volumetric Octree ($\pm 4\text{ Mpc}$ to $\pm 15\text{ kpc}$ BCG Cores)

Every cluster volume is deposited using a mass-conserving 3D SPH/Voronoi kernel into **five nested $256^3$ octree levels** (`tng50-viz/2` schema) and ray-marched in a single WebGL2 GLSL3 pass:

| Level | Half-Box Extent | Full Box Span | Voxel Size ($256^3$) | Astrophysical Regime |
| :---: | :---: | :---: | :---: | :--- |
| **`L0` / `S0`** | $\pm 4000\text{ kpc}$ | $8.0\text{ Mpc}$ | $31.25\text{ kpc}$ | Accretion shocks, infalling filaments, cosmic web splashback ($2\text{--}3\,R_{200c}$) |
| **`L1` / `S1`** | $\pm 1000\text{ kpc}$ | $2.0\text{ Mpc}$ | $7.81\text{ kpc}$ | Bulk virialized Intracluster Medium ($R_{200c}$) & infalling subclusters |
| **`L2` / `S2`** | $\pm 250\text{ kpc}$ | $500\text{ kpc}$ | $1.95\text{ kpc}$ | Cool-core / sloshing cold fronts, ram-pressure stripped tails |
| **`L3` / `S3`** | $\pm 62.5\text{ kpc}$ | $125\text{ kpc}$ | $488\text{ pc}$ | Circum-BCG multiphase condensation & AGN X-ray cavity rims |
| **`L4` / `S4`** | $\pm 15.0\text{ kpc}$ | $30\text{ kpc}$ | $117\text{ pc}$ | Brightest Cluster Galaxy (BCG) core, multiphase filaments & cold dust |

### 18 Volumetric 3D Fields + 5 Real-Time Kinematic Views
- **Thermodynamic Gas Fields (`3`):** Hydrogen number density $n_{\text{H}}$, $n_{\text{H}}$-weighted temperature $T$, and metallicity $Z/Z_\odot$.
- **12 UV / EUV / X-Ray Ion Number Densities (`12`):**
  $\text{H I } 1216$, $\text{Mg II } 2796$, $\text{Si II } 1260$, $\text{C II } 1335$, $\text{Si III } 1206$, $\text{C III } 977$, $\text{Si IV } 1403$, $\text{C IV } 1548$, $\text{N V } 1239$, $\text{O VI } 1032$, $\text{Ne VIII } 770$, and $\text{O VII } 21.6\text{ \AA}$.
- **3D Velocity Vector Cubes (`vx`, `vy`, `vz`) $\to$ 5 Real-Time Kinematic Views:**
  Line-of-sight velocity $v_{\text{los}}$, radial inflow/outflow velocity $v_r$, rotational velocity $v_\phi$, 3D speed $|v|$, and line-of-sight velocity dispersion $\sigma_{\text{los}}$.
- **BCG & Satellite Starlight (`S0..S4`):** True-colour SDSS $g, r, i$ Lupton et al. (2004) asinh surface-brightness composite with 3D dust radiative transfer.

---

## Live Hugging Face Dataset Packs

- **[`tanmay-starslab/icm-atlas-web-0`](https://huggingface.co/datasets/tanmay-starslab/icm-atlas-web-0)**: 120-ray TNGS v2 binary absorption spectra (`s/*.bin`), Voigt component catalogs (`components.json`), sightline catalogs (`catalog.json`), `galaxy.json`, and `viz/manifest_v2.json`.
- **[`tanmay-starslab/icm-atlas-3d-0`](https://huggingface.co/datasets/tanmay-starslab/icm-atlas-3d-0)**: 5-level ($256^3$) lossless WebP 3D volumetric texture atlases (`L0..L4` gas, 12 ions, 3D velocities, and `S0..S4` stellar composites).

---

## Local Development & Building

```bash
# Rebuild the 382-cluster catalog and static site (docs/ and dist/)
python3 deploy/data/build_icm_catalog.py

# Serve locally
python3 -m http.server 8000 --directory docs
```

## License & Credits

Code released under the [MIT License](LICENSE). Simulation credits: IllustrisTNG Collaboration (Nelson et al. 2019a, 2024; Pillepich et al. 2018; Springel et al. 2018) and SIMBA Collaboration (Davé et al. 2019).
