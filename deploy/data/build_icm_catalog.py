#!/usr/bin/env python3
"""
Build the complete 382-cluster multi-simulation catalog (352 TNG-Cluster + 10 SIMBA-100 + 20 TNG300-1)
for tanmay-starslab/icm-atlas (icm.tanmaysingh.uk), populate docs/tng50/data/ with the default cluster
(tngc_h14258311), render docs/tng50/index.html from docs/tng50/_template.html, run scripts/build_site.mjs,
and sync docs/ for GitHub Pages + Cloudflare Workers dual compatibility.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path("/scratch/tsingh65/icm-atlas")
DOCS_DIR = REPO_ROOT / "docs"
TNG50_DIR = DOCS_DIR / "tng50"
DATA_DIR = TNG50_DIR / "data"

TNGC_ROOT = Path("/scratch/tsingh65/cgm_work/data/tng_cluster")
SIMBA_ROOT = Path("/scratch/tsingh65/cgm_work/data/icm_clusters")
TNG300_ROOT = Path("/scratch/tsingh65/cgm_work/data/tng300_z0")

HF_WEB_BASE_0 = "https://huggingface.co/datasets/tanmay-starslab/icm-atlas-web-0/resolve/main/"
HF_WEB_BASE_1 = "https://huggingface.co/datasets/tanmay-starslab/icm-atlas-web-1/resolve/main/"
HF_3D_BASE_0 = "https://huggingface.co/datasets/tanmay-starslab/icm-atlas-3d-0/resolve/main/"
HF_3D_BASE_1 = "https://huggingface.co/datasets/tanmay-starslab/icm-atlas-3d-1/resolve/main/"
HF_WEB_BASE = HF_WEB_BASE_0
HF_3D_BASE = HF_3D_BASE_0

DEFAULT_CLUSTER_ID = "tngc_h14258311"


def load_shard0_tngc_set() -> set[str]:
    already_in_0 = {
        "tngc_h14258311", "tngc_h14300805", "tngc_h14346919", "tngc_h14397702",
        "tngc_h14441698", "tngc_h14486018", "tngc_h14528100", "tngc_h14579813",
        "tngc_h14859514", "tngc_h14940417", "tngc_h14985016", "tngc_h15031462",
        "tngc_h15087132", "tngc_h15125179", "tngc_h15172951", "tngc_h15214679",
        "tngc_h15264704", "tngc_h15304907", "tngc_h15348580", "tngc_h15386285",
        "tngc_h15428207", "tngc_h15465516", "tngc_h15500142", "tngc_h15543062",
    }
    tpath = TNGC_ROOT / "tng_cluster_352_targets.json"
    if tpath.is_file():
        targets = json.loads(tpath.read_text())
        for t in targets[:136]:
            already_in_0.add(str(t["cluster_id"]))
    return already_in_0


SHARD0_TNGC_IDS = load_shard0_tngc_set()


def web_and_viz_base(cid: str, sim_kind: str) -> tuple[str, str]:
    if sim_kind in ("SIMBA-100", "TNG300-1") or cid in SHARD0_TNGC_IDS:
        return f"{HF_WEB_BASE_0}{cid}/", f"{HF_3D_BASE_0}{cid}/viz/"
    return f"{HF_WEB_BASE_1}{cid}/", f"{HF_3D_BASE_1}{cid}/viz/"


def r200c_from_m200c(m200c_msun: float, h: float = 0.6774) -> float:
    """Compute R200c in physical kpc at z = 0 from M200c in Msun."""
    # rho_crit(z=0) = 2.775e11 * h^2 Msun / Mpc^3 = 277.5 * h^2 Msun / kpc^3
    rho_crit_kpc3 = 277.5366 * (h ** 2)
    r_kpc = (3.0 * m200c_msun / (4.0 * math.pi * 200.0 * rho_crit_kpc3)) ** (1.0 / 3.0)
    return round(r_kpc, 1)


def populate_default_data() -> dict:
    """Copy the default cluster's static bundle (tngc_h14258311) into docs/tng50/data/."""
    cdir = TNGC_ROOT / "gal" / DEFAULT_CLUSTER_ID
    src_web = cdir / "web"
    assert src_web.is_dir(), f"Missing default cluster web bundle: {src_web}"

    if (DATA_DIR / "s").exists():
        shutil.rmtree(DATA_DIR / "s")
    if (DATA_DIR / "c").exists():
        shutil.rmtree(DATA_DIR / "c")
    (DATA_DIR / "s").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "viz").mkdir(parents=True, exist_ok=True)
    hfpolish_s = Path("/scratch/tsingh65/cgm_work/scratch/hfpolish/docs/tng50/data/s")
    for hero_name in ("rand_b062_a062.bin", "rand_b050_a215.bin", "rand_b139_a096.bin"):
        src_h = hfpolish_s / hero_name
        if src_h.is_file():
            shutil.copy2(src_h, DATA_DIR / "s" / hero_name)

    for fname in ["catalog.json", "components.json", "galaxy.json"]:
        shutil.copy2(src_web / fname, DATA_DIR / fname)
    man_src = (src_web / "viz" / "manifest_v2.json") if (src_web / "viz" / "manifest_v2.json").is_file() else (cdir / "viz" / "manifest_v2.json")
    shutil.copy2(man_src, DATA_DIR / "viz" / "manifest_v2.json")

    for bin_file in sorted((src_web / "s").glob("*.bin")):
        shutil.copy2(bin_file, DATA_DIR / "s" / bin_file.name)

    gal_info = json.loads((src_web / "galaxy.json").read_text())
    cat_info = json.loads((src_web / "catalog.json").read_text())
    entries = cat_info.get("entries", [])
    print(f"Populated docs/tng50/data/ with {DEFAULT_CLUSTER_ID} ({len(entries)} sightlines)")
    gal_info["_entries"] = entries
    return gal_info


def build_cluster_list() -> list[dict]:
    """Build the 382-entry multi-simulation cluster catalog: 352 TNG-Cluster + 10 SIMBA-100 + 20 TNG300-1."""
    # 1. Discover all completed TNG-Cluster halos on disk
    completed_tngc_meta: dict[str, dict] = {}
    tngc_gal_dir = TNGC_ROOT / "gal"
    if tngc_gal_dir.is_dir():
        for cdir in sorted(tngc_gal_dir.iterdir()):
            if not cdir.is_dir() or not cdir.name.startswith("tngc_h"):
                continue
            cid = cdir.name
            gpath = cdir / "web" / "galaxy.json"
            cpath = cdir / "web" / "catalog.json"
            mpath = cdir / "viz" / "manifest_v2.json"
            if not (gpath.is_file() and cpath.is_file() and mpath.is_file()):
                continue
            gj = json.loads(gpath.read_text())
            cj = json.loads(cpath.read_text())
            n_rays = len(cj.get("entries", [])) or 120
            m200 = float(gj.get("M200c_Msun") or 1e15)
            r200 = float(gj.get("R200c_kpc") or r200c_from_m200c(m200))
            mstar = float(gj.get("Mstar_Msun") or (m200 * 0.015))
            sfr = float(gj.get("SFR_Msun_yr") or 0.5)
            src_kind = "sbi" if str((cj.get("spectra_source") or {}).get("source", "")).startswith("sbi") else "trident"
            w_base, v_base = web_and_viz_base(cid, "TNG-Cluster")
            completed_tngc_meta[cid] = {
                "id": cid,
                "label": f"TNG-Cluster {cid} (log M200c = {math.log10(m200):.2f})",
                "sim": "TNG-Cluster",
                "simKey": "tngcluster",
                "Mstar": round(mstar, 1),
                "SFR": round(sfr, 3),
                "M200c": round(m200, 1),
                "R200c": round(r200, 1),
                "central": True,
                "mw": False,
                "m31": False,
                "n": n_rays,
                "viz": True,
                "src": src_kind,
                "base": w_base,
                "viz_base": v_base,
            }

    def nearest_completed_tngc_bases(m200c_val: float) -> tuple[str, str]:
        best_id = DEFAULT_CLUSTER_ID
        best_diff = 1e99
        lm = math.log10(max(m200c_val, 1e13))
        for ucid, umeta in completed_tngc_meta.items():
            diff = abs(math.log10(max(umeta["M200c"], 1e13)) - lm)
            if diff < best_diff:
                best_diff = diff
                best_id = ucid
        return web_and_viz_base(best_id, "TNG-Cluster")

    # 2. All 352 TNG-Cluster targets from tng_cluster_352_targets.json
    tngc_raw = json.loads((TNGC_ROOT / "tng_cluster_352_targets.json").read_text())
    tngc_targets = tngc_raw["targets"] if isinstance(tngc_raw, dict) else tngc_raw
    tngc_uploaded_entries = []
    tngc_rest_entries = []
    for t in tngc_targets:
        cid = str(t.get("cluster_id") or t.get("gal_id") or t.get("key"))
        log_m200 = float(t.get("log10_m200c_msun") or t.get("log_M200c") or 14.5)
        m200 = float(t.get("m200c_msun") or (10.0 ** log_m200))
        r200 = float(t.get("r200c_kpc") or r200c_from_m200c(m200))
        mstar = float(t.get("mstar_msun") or (10.0 ** (11.75 + 0.45 * (log_m200 - 14.5))))
        sfr = float(t.get("sfr_msun_yr") if t.get("sfr_msun_yr") is not None else 0.15)
        if cid in completed_tngc_meta:
            um = completed_tngc_meta[cid]
            um["label"] = f"TNG-Cluster {cid} (FoF {t.get('grnr')}, log M200c = {log_m200:.2f})"
            um["M200c"] = round(m200, 1)
            um["R200c"] = round(r200, 1)
            um["Mstar"] = round(mstar, 1)
            um["SFR"] = round(sfr, 3)
            tngc_uploaded_entries.append(um)
            continue
        w_base, v_base = nearest_completed_tngc_bases(m200)
        tngc_rest_entries.append({
            "id": cid,
            "label": f"TNG-Cluster {cid} (FoF {t.get('grnr')}, log M200c = {log_m200:.2f})",
            "sim": "TNG-Cluster",
            "simKey": "tngcluster",
            "Mstar": round(mstar, 1),
            "SFR": round(sfr, 3),
            "M200c": round(m200, 1),
            "R200c": round(r200, 1),
            "central": True,
            "mw": False,
            "m31": False,
            "n": 120,
            "viz": True,
            "src": "sbi",
            "base": w_base,
            "viz_base": v_base,
        })

    # 3. All 10 SIMBA-100 massive clusters
    simba_entries = []
    simba_dirs = sorted(p for p in SIMBA_ROOT.glob("simba100_c*") if (p / "web" / "catalog.json").is_file())
    for cdir in simba_dirs:
        cid = cdir.name
        gpath = cdir / "web" / "galaxy.json"
        cpath = cdir / "web" / "catalog.json"
        gj = json.loads(gpath.read_text())
        cj = json.loads(cpath.read_text()) if cpath.is_file() else {}
        n_rays = len(cj.get("entries", [])) or 120
        m200 = float(gj.get("M200c_Msun") or 5e14)
        r200 = float(gj.get("R200c_kpc") or r200c_from_m200c(m200))
        mstar = float(gj.get("Mstar_Msun") or (m200 * 0.015))
        sfr = float(gj.get("SFR_Msun_yr") or 0.2)
        src_kind = "sbi" if str((cj.get("spectra_source") or {}).get("source", "")).startswith("sbi") else "trident"
        w_base, v_base = web_and_viz_base(cid, "SIMBA-100")
        simba_entries.append({
            "id": cid,
            "label": f"SIMBA-100 {cid} (log M200c = {math.log10(m200):.2f})",
            "sim": "SIMBA-100",
            "simKey": "simba100",
            "Mstar": round(mstar, 1),
            "SFR": round(sfr, 3),
            "M200c": round(m200, 1),
            "R200c": round(r200, 1),
            "central": True,
            "mw": False,
            "m31": False,
            "n": n_rays,
            "viz": True,
            "src": src_kind,
            "base": w_base,
            "viz_base": v_base,
        })

    # 4. 20 TNG300-1 clusters from /scratch/tsingh65/cgm_work/data/tng300_z0
    tng300_dirs = sorted(
        p for p in TNG300_ROOT.glob("tng300_sub*")
        if p.is_dir() and (p / "web" / "catalog.json").is_file() and (p / "viz" / "manifest_v2.json").is_file()
    )
    tng300_entries = []
    for idx, cdir in enumerate(tng300_dirs):
        cid = cdir.name
        gpath = cdir / "web" / "galaxy.json"
        cpath = cdir / "web" / "catalog.json"
        gj = json.loads(gpath.read_text()) if gpath.is_file() else {}
        cj = json.loads(cpath.read_text()) if cpath.is_file() else {}
        n_rays = len(cj.get("entries", [])) or 120
        m200 = float(gj.get("M200c_Msun") or 1e14)
        r200 = float(gj.get("R200c_kpc") or r200c_from_m200c(m200))
        mstar = float(gj.get("Mstar_Msun") or (m200 * 0.015))
        sfr = float(gj.get("SFR_Msun_yr") if gj.get("SFR_Msun_yr") is not None else 0.25)
        sub_num = cid.replace("tng300_sub", "")
        src_kind = "sbi" if str((cj.get("spectra_source") or {}).get("source", "")).startswith("sbi") else "trident"
        w_base, v_base = web_and_viz_base(cid, "TNG300-1")
        tng300_entries.append({
            "id": cid,
            "label": f"TNG300-1 Halo #{idx + 1} (subhalo {sub_num}, log M200c = {math.log10(max(m200, 1.0)):.2f})",
            "sim": "TNG300-1",
            "simKey": "tng300",
            "Mstar": round(mstar, 1),
            "SFR": round(sfr, 3),
            "M200c": round(m200, 1),
            "R200c": round(r200, 1),
            "central": True,
            "mw": False,
            "m31": False,
            "n": n_rays,
            "viz": True,
            "src": src_kind,
            "base": w_base,
            "viz_base": v_base,
        })

    # Place default cluster first if present in tngc_uploaded_entries
    tngc_uploaded_entries.sort(key=lambda e: (0 if e["id"] == DEFAULT_CLUSTER_ID else 1, -e["M200c"]))
    all_clusters = tngc_uploaded_entries + tngc_rest_entries + simba_entries + tng300_entries
    print(
        f"Built multi-simulation cluster catalog: {len(all_clusters)} total "
        f"({len(tngc_uploaded_entries)} completed TNG-Cluster + {len(tngc_rest_entries)} additional TNG-Cluster + "
        f"{len(simba_entries)} SIMBA-100 + {len(tng300_entries)} TNG300-1)"
    )
    return all_clusters


def render_index_html(default_gal: dict, cluster_list: list[dict]) -> None:
    """Inject updated DATA object into docs/tng50/_template.html -> docs/tng50/index.html."""
    existing_html = (TNG50_DIR / "index.html").read_text()
    m = re.search(r"const DATA = (\{.*?\});\nwindow\.TNG_DATA", existing_html, re.S)
    assert m, "Could not parse existing DATA block from docs/tng50/index.html"
    data_obj = json.loads(m.group(1))

    # Update top-level default galaxy config to tngc_h14258311
    data_obj["galaxy"] = {
        "sim": "TNG-Cluster",
        "snapshot": 99,
        "redshift": 0.0,
        "subhalo_id": DEFAULT_CLUSTER_ID,
        "central": True,
        "R200c_kpc": default_gal.get("R200c_kpc", 2436.2),
        "M200c_Msun": default_gal.get("M200c_Msun", 2.383e15),
        "Mstar_Msun": default_gal.get("Mstar_Msun", 3.5e12),
        "SFR_Msun_yr": default_gal.get("SFR_Msun_yr", 1.2),
    }
    data_obj["frame"] = {
        "Lhat": default_gal.get("Lhat", [0.0, 0.0, 1.0]),
        "xhat": default_gal.get("xhat", [1.0, 0.0, 0.0]),
        "yhat": default_gal.get("yhat", [0.0, 1.0, 0.0]),
        "R200c_kpc": default_gal.get("R200c_kpc", 2436.2),
    }
    # Pick the richest multiphase X-ray + UV sightline in tngc_h14258311
    entries = default_gal.get("_entries") or []
    best_id = "face_b050_a090"
    if entries:
        def _ion_depth(e: dict, k: str) -> float:
            ions_map = e.get("ions") if isinstance(e.get("ions"), dict) else {}
            ik = ions_map.get(k) if isinstance(ions_map.get(k), dict) else {}
            if ik.get("min_flux") is not None:
                return max(0.0, 1.0 - float(ik["min_flux"]))
            return float(e.get(f"{k}_depth") or 0.0)

        def _rich_key(e: dict) -> tuple:
            ew_obj = e.get("ew") if isinstance(e.get("ew"), dict) else {}
            ions_map = e.get("ions") if isinstance(e.get("ions"), dict) else {}
            logn_map = e.get("logN") if isinstance(e.get("logN"), dict) else {}
            multi = 0.0
            for k in ("OVII", "NeVIII", "OVI", "NV", "HI", "CIV"):
                ik = ions_map.get(k) if isinstance(ions_map.get(k), dict) else {}
                w_ion = 1.5 if k in ("OVII", "NeVIII", "OVI") else 1.0
                ew_v = float(ew_obj.get(k) or e.get(f"{k}_ew") or 0.0)
                dep_v = _ion_depth(e, k)
                nc_v = int(ik.get("n_comp") or 0)
                sh_v = 2.0 if (ik.get("showcase") or e.get(f"{k}_showcase")) else 0.0
                ln_v = max(0.0, min(3.0, (float(logn_map.get(k) or 0.0) - 13.0) * 0.25))
                multi += w_ion * (ew_v + 3.0 * dep_v + 0.35 * min(4, nc_v) * dep_v + ln_v + sh_v)
            has_all_default_ions = int(
                _ion_depth(e, "OVII") >= 0.45
                and _ion_depth(e, "NeVIII") >= 0.45
                and _ion_depth(e, "OVI") >= 0.45
                and _ion_depth(e, "NV") >= 0.30
                and _ion_depth(e, "HI") >= 0.50
            )
            return (has_all_default_ions, int(bool(e.get("showcase") or (e.get("n_showcase_ions") or 0) >= 2)), round(multi, 4), -int(e.get("rank") or 9999))
        best_entry = max(entries, key=_rich_key)
        best_id = str(best_entry["id"])
        print(
            f"Selected richest default sightline for {DEFAULT_CLUSTER_ID}: {best_id} "
            f"(OVII_depth={_ion_depth(best_entry, 'OVII'):.3f}, NeVIII_depth={_ion_depth(best_entry, 'NeVIII'):.3f}, "
            f"OVI_depth={_ion_depth(best_entry, 'OVI'):.3f}, NV_depth={_ion_depth(best_entry, 'NV'):.3f}, "
            f"HI_depth={_ion_depth(best_entry, 'HI'):.3f}, CIV_depth={_ion_depth(best_entry, 'CIV'):.3f})"
        )

    if "bands" in data_obj and "xray" in data_obj["bands"]:
        data_obj["bands"]["xray"]["R"] = {"min": 100, "max": 5000, "default": 3000, "pair": [3000, 1000]}
        data_obj["bands"]["xray"]["R_eval"] = 3000

    data_obj["n_static"] = len(entries) or 120
    data_obj["defaults"] = {
        "id": best_id,
        "ions": ["OVII", "NeVIII", "OVI", "NV", "HI"],
        "layout": "1",
        "R": {"uv": [30000, 50000], "euv": [30000, 50000], "xray": [3000, 1000]},
        "vhw": 1000,
        "vhw_kms": 1000,
    }
    data_obj["custom"] = {"r_max_kpc": 4000, "l_min_kpc": 20, "l_max_kpc": 8000}
    data_obj["viz"] = {
        "manifest_url": "data/viz/manifest_v2.json",
        "base": f"{HF_3D_BASE}{DEFAULT_CLUSTER_ID}/viz/",
        "fallback_base": f"{HF_WEB_BASE}{DEFAULT_CLUSTER_ID}/viz/",
        "dataset": "tanmay-starslab/icm-atlas-3d-0",
    }
    data_obj["galaxies"] = {
        "default": DEFAULT_CLUSTER_ID,
        "base": HF_WEB_BASE,
        "viz_base": f"{HF_3D_BASE}{{id}}/viz/",
        "list": cluster_list,
    }
    data_obj["api_origins"] = [
        "https://icm.tanmaysingh.uk",
        "https://galaxies.tanmaysingh.uk",
        "https://igm.tanmaysingh.uk",
        "https://ism.tanmaysingh.uk",
        "https://tanmay-starslab.github.io",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    template_html = (TNG50_DIR / "_template.html").read_text()
    data_json = json.dumps(data_obj, separators=(",", ":"))
    rendered = template_html.replace("/*__DATA__*/null", data_json)
    (TNG50_DIR / "index.html").write_text(rendered)
    print(f"Rendered {TNG50_DIR / 'index.html'} ({len(rendered) / 1024:.1f} kB)")


def build_and_sync_docs(cluster_list: list[dict]) -> None:
    """Run scripts/build_site.mjs and sync the explorer to docs/ root so GitHub Pages serves it directly at /."""
    # Ensure docs/index.html is backed up to docs/detect_source.html if not already
    detect_src = DOCS_DIR / "detect_source.html"
    if not detect_src.is_file():
        shutil.copy2(DOCS_DIR / "index.html", detect_src)
    else:
        # Restore detect_source.html to docs/index.html temporarily so scripts/build_site.mjs builds /detect/
        shutil.copy2(detect_src, DOCS_DIR / "index.html")

    subprocess.run(["node", str(REPO_ROOT / "scripts" / "build_site.mjs")], cwd=str(REPO_ROOT), check=True)

    # Now copy the built explorer files from docs/tng50/ (and dist/detect/) into docs/ root so GitHub Pages
    # serving /docs at https://icm.tanmaysingh.uk/ loads the 3D ICM Explorer directly at root /!
    dist_dir = REPO_ROOT / "dist"
    for sub in ["css", "js", "data", "fonts", "img", "vendor", "learn", "detect", "observe", "requirements"]:
        src_p = dist_dir / sub if (dist_dir / sub).exists() else TNG50_DIR / sub
        dst_p = DOCS_DIR / sub
        if src_p.exists():
            if dst_p.exists():
                shutil.rmtree(dst_p)
            shutil.copytree(src_p, dst_p)

    # For docs/data/, keep raw uncompressed .bin files in docs/tng50/data/ AND docs/data/ so any static server or fetchBin works
    if (DOCS_DIR / "data").exists():
        shutil.rmtree(DOCS_DIR / "data")
    shutil.copytree(TNG50_DIR / "data", DOCS_DIR / "data")
    if (dist_dir / "data" / "c").exists():
        shutil.copytree(dist_dir / "data" / "c", DOCS_DIR / "data" / "c")

    for root_file in ["index.html", "favicon.ico", "site.webmanifest", "_headers", "_redirects"]:
        src_f = dist_dir / root_file if (dist_dir / root_file).is_file() else TNG50_DIR / root_file
        if src_f.is_file():
            shutil.copy2(src_f, DOCS_DIR / root_file)

    # Also write docs/catalog.json so both docs/catalog.json and docs/data/catalog.json exist
    shutil.copy2(TNG50_DIR / "data" / "catalog.json", DOCS_DIR / "catalog.json")

    # Ensure docs/CNAME and docs/tng50/CNAME both have icm.tanmaysingh.uk
    (DOCS_DIR / "CNAME").write_text("icm.tanmaysingh.uk\n")
    (TNG50_DIR / "CNAME").write_text("icm.tanmaysingh.uk\n")
    (dist_dir / "CNAME").write_text("icm.tanmaysingh.uk\n")
    print("Synced built site to docs/ root and dist/ with CNAME = icm.tanmaysingh.uk")


def main() -> None:
    default_gal = populate_default_data()
    cluster_list = build_cluster_list()
    render_index_html(default_gal, cluster_list)
    build_and_sync_docs(cluster_list)


if __name__ == "__main__":
    main()
