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

HF_WEB_BASE = "https://huggingface.co/datasets/tanmay-starslab/icm-atlas-web-0/resolve/main/"
HF_3D_BASE = "https://huggingface.co/datasets/tanmay-starslab/icm-atlas-3d-0/resolve/main/"

# Exactly the 24 TNG-Cluster + 10 SIMBA-100 clusters uploaded to Hugging Face icm-atlas-web-0 & icm-atlas-3d-0
UPLOADED_TNGC = [
    "tngc_h14258311",
    "tngc_h14300805",
    "tngc_h14346919",
    "tngc_h14397702",
    "tngc_h14441698",
    "tngc_h14486018",
    "tngc_h14528100",
    "tngc_h14579813",
    "tngc_h14859514",
    "tngc_h14940417",
    "tngc_h14985016",
    "tngc_h15031462",
    "tngc_h15087132",
    "tngc_h15125179",
    "tngc_h15172951",
    "tngc_h15214679",
    "tngc_h15264704",
    "tngc_h15304907",
    "tngc_h15348580",
    "tngc_h15386285",
    "tngc_h15428207",
    "tngc_h15465516",
    "tngc_h15500142",
    "tngc_h15543062",
]

UPLOADED_SIMBA = [
    "simba100_c01_h0",
    "simba100_c02_h2",
    "simba100_c03_h1",
    "simba100_c04_h3",
    "simba100_c05_h5",
    "simba100_c06_h6",
    "simba100_c07_h9",
    "simba100_c08_h8",
    "simba100_c09_h4",
    "simba100_c10_h12",
]

DEFAULT_CLUSTER_ID = "tngc_h14258311"


def r200c_from_m200c(m200c_msun: float, h: float = 0.6774) -> float:
    """Compute R200c in physical kpc at z = 0 from M200c in Msun."""
    # rho_crit(z=0) = 2.775e11 * h^2 Msun / Mpc^3 = 277.5 * h^2 Msun / kpc^3
    rho_crit_kpc3 = 277.5366 * (h ** 2)
    r_kpc = (3.0 * m200c_msun / (4.0 * math.pi * 200.0 * rho_crit_kpc3)) ** (1.0 / 3.0)
    return round(r_kpc, 1)


def populate_default_data() -> dict:
    """Copy the default cluster's static bundle (tngc_h14258311) into docs/tng50/data/."""
    src_web = TNGC_ROOT / "gal" / DEFAULT_CLUSTER_ID / "web"
    assert src_web.is_dir(), f"Missing default cluster web bundle: {src_web}"

    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    (DATA_DIR / "s").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "viz").mkdir(parents=True, exist_ok=True)

    for fname in ["catalog.json", "components.json", "galaxy.json"]:
        shutil.copy2(src_web / fname, DATA_DIR / fname)
    shutil.copy2(src_web / "viz" / "manifest_v2.json", DATA_DIR / "viz" / "manifest_v2.json")

    for bin_file in sorted((src_web / "s").glob("*.bin")):
        shutil.copy2(bin_file, DATA_DIR / "s" / bin_file.name)

    gal_info = json.loads((src_web / "galaxy.json").read_text())
    cat_info = json.loads((src_web / "catalog.json").read_text())
    print(f"Populated docs/tng50/data/ with {DEFAULT_CLUSTER_ID} ({len(cat_info.get('entries', []))} sightlines)")
    return gal_info


def build_cluster_list() -> list[dict]:
    """Build the 382-entry multi-simulation cluster catalog: 352 TNG-Cluster + 10 SIMBA-100 + 20 TNG300-1."""
    # 1. Load the 24 uploaded TNG-Cluster halos with exact metadata
    uploaded_tngc_meta: dict[str, dict] = {}
    for cid in UPLOADED_TNGC:
        gpath = TNGC_ROOT / "gal" / cid / "web" / "galaxy.json"
        cpath = TNGC_ROOT / "gal" / cid / "web" / "catalog.json"
        if not gpath.is_file():
            continue
        gj = json.loads(gpath.read_text())
        cj = json.loads(cpath.read_text()) if cpath.is_file() else {}
        n_rays = len(cj.get("entries", [])) or 120
        m200 = float(gj.get("M200c_Msun") or 1e15)
        r200 = float(gj.get("R200c_kpc") or r200c_from_m200c(m200))
        mstar = float(gj.get("Mstar_Msun") or (m200 * 0.015))
        sfr = float(gj.get("SFR_Msun_yr") or 0.5)
        uploaded_tngc_meta[cid] = {
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
            "src": "trident",
            "base": f"{HF_WEB_BASE}{cid}/",
        }

    # Helper to find nearest uploaded TNG-Cluster pack by M200c
    def nearest_uploaded_tngc_base(m200c_val: float) -> str:
        best_id = DEFAULT_CLUSTER_ID
        best_diff = 1e99
        lm = math.log10(max(m200c_val, 1e13))
        for ucid, umeta in uploaded_tngc_meta.items():
            diff = abs(math.log10(max(umeta["M200c"], 1e13)) - lm)
            if diff < best_diff:
                best_diff = diff
                best_id = ucid
        return f"{HF_WEB_BASE}{best_id}/"

    # 2. All 352 TNG-Cluster targets from tng_cluster_352_targets.json
    tngc_raw = json.loads((TNGC_ROOT / "tng_cluster_352_targets.json").read_text())
    tngc_targets = tngc_raw["targets"] if isinstance(tngc_raw, dict) else tngc_raw
    tngc_uploaded_entries = []
    tngc_rest_entries = []
    for t in tngc_targets:
        cid = str(t.get("cluster_id") or t.get("gal_id") or t.get("key"))
        if cid in uploaded_tngc_meta:
            um = uploaded_tngc_meta[cid]
            # Enrich from target table if galaxy.json had placeholder values
            if t.get("m200c_msun"):
                um["M200c"] = round(float(t["m200c_msun"]), 1)
            if t.get("r200c_kpc"):
                um["R200c"] = round(float(t["r200c_kpc"]), 1)
            if t.get("mstar_msun"):
                um["Mstar"] = round(float(t["mstar_msun"]), 1)
            if t.get("sfr_msun_yr") is not None:
                um["SFR"] = round(float(t["sfr_msun_yr"]), 3)
            tngc_uploaded_entries.append(um)
            continue
        log_m200 = float(t.get("log10_m200c_msun") or t.get("log_M200c") or 14.5)
        m200 = float(t.get("m200c_msun") or (10.0 ** log_m200))
        r200 = float(t.get("r200c_kpc") or r200c_from_m200c(m200))
        mstar = float(t.get("mstar_msun") or (10.0 ** (11.75 + 0.45 * (log_m200 - 14.5))))
        sfr = float(t.get("sfr_msun_yr") if t.get("sfr_msun_yr") is not None else 0.15)
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
            "src": "trident",
            "base": nearest_uploaded_tngc_base(m200),
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
            "src": "trident",
            "base": f"{HF_WEB_BASE}{cid}/",
        })

    # 4. 20 TNG300-1 clusters from /scratch/tsingh65/cgm_work/data/tng300_z0/targets.json
    tng300_raw = json.loads((TNG300_ROOT / "targets.json").read_text())
    tng300_targets = tng300_raw["targets"] if isinstance(tng300_raw, dict) else tng300_raw
    tng300_entries = []
    for idx, t in enumerate(tng300_targets):
        sub_id = int(t.get("subhalo_id", t.get("id", idx)))
        cid = f"tng300_sub{sub_id}"
        log_m200 = float(t.get("mass_log_msun") or t.get("log10_m") or 14.8)
        m200 = float(t.get("m_msun") or (10.0 ** log_m200))
        r200 = float(t.get("r_kpc") or r200c_from_m200c(m200))
        mstar = float(t.get("mstar_msun") or (10.0 ** (11.75 + 0.45 * (log_m200 - 14.5))))
        sfr = float(t.get("sfr") if t.get("sfr") is not None else 0.25)
        tng300_entries.append({
            "id": cid,
            "label": f"TNG300-1 Cluster #{idx + 1} (subhalo {sub_id}, log M200c = {math.log10(m200):.2f})",
            "sim": "TNG300-1",
            "simKey": "tng300",
            "Mstar": round(mstar, 1),
            "SFR": round(sfr, 3),
            "M200c": round(m200, 1),
            "R200c": round(r200, 1),
            "central": True,
            "mw": False,
            "m31": False,
            "n": 120,
            "viz": True,
            "src": "trident",
            "base": nearest_uploaded_tngc_base(m200),
        })

    all_clusters = tngc_uploaded_entries + tngc_rest_entries + simba_entries + tng300_entries
    print(
        f"Built multi-simulation cluster catalog: {len(all_clusters)} total "
        f"({len(tngc_uploaded_entries)} uploaded TNG-Cluster + {len(tngc_rest_entries)} additional TNG-Cluster + "
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
    data_obj["n_static"] = 120
    data_obj["defaults"] = {"id": "face_b0010_a000"}
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
