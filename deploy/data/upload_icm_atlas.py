#!/usr/bin/env python3
"""Upload the 10 completed SIMBA-100 ICM cluster 3D + 120-ray bundles
(/scratch/tsingh65/cgm_work/data/icm_clusters/) and the completed TNG-Cluster 3D + 120-ray bundles
(/scratch/tsingh65/cgm_work/data/tng_cluster/gal/) to Hugging Face datasets:
  - tanmay-starslab/icm-atlas-web-0 (complete web + 5-level WebP 3D + 120-ray TNGS v2 pack for every cluster)
  - tanmay-starslab/icm-atlas-3d-0  (5-level WebP 3D + manifest_v2.json + luts.json + galaxy.json pack for every cluster)
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path("/scratch/tsingh65/icm-atlas")
if not REPO_ROOT.is_dir():
    REPO_ROOT = Path("/scratch/tsingh65/cgm_work/scratch/hfpolish")
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "deploy" / "data"))

from tngsight import vizpack as VP  # noqa: E402
import upload_galaxies as U  # noqa: E402
import upload_viz_dataset as V  # noqa: E402
from huggingface_hub import CommitOperationAdd, HfApi  # noqa: E402

ICM_GAS_LEVELS = {"L0": 4000.0, "L1": 1000.0, "L2": 250.0, "L3": 62.5, "L4": 15.0}
ICM_STAR_LEVELS = {"S0": 4000.0, "S1": 1000.0, "S2": 250.0, "S3": 62.5, "S4": 15.0}
VP.ALL_GAS_LEVELS = dict(ICM_GAS_LEVELS)
VP.GAS_LEVELS = dict(ICM_GAS_LEVELS)
VP.ALL_STAR_LEVELS = dict(ICM_STAR_LEVELS)
VP.STAR_LEVELS = dict(ICM_STAR_LEVELS)
VP.R_MASK_KPC = {}

SIMBA_ROOT = Path("/scratch/tsingh65/cgm_work/data/icm_clusters")
TNG300_ROOT = Path("/scratch/tsingh65/cgm_work/data/tng300_z0")
TNGC_ROOT = Path("/scratch/tsingh65/cgm_work/data/tng_cluster/gal")
TNGC_TARGETS_JSON = Path("/scratch/tsingh65/cgm_work/data/tng_cluster/tng_cluster_352_targets.json")

WEB_REPOS = {
    0: "tanmay-starslab/icm-atlas-web-0",
    1: "tanmay-starslab/icm-atlas-web-1",
}
VIZ3D_REPOS = {
    0: "tanmay-starslab/icm-atlas-3d-0",
    1: "tanmay-starslab/icm-atlas-3d-1",
}


def load_shard0_tngc_set() -> set[str]:
    """Keep the first 160 TNG-Cluster targets (indices 0..159) + all UPLOADED_TNGC in shard 0,
    and place the remaining TNG-Cluster targets in shard 1 so each repo stays <95,000 files."""
    already_in_0 = {
        "tngc_h14258311", "tngc_h14300805", "tngc_h14346919", "tngc_h14397702",
        "tngc_h14441698", "tngc_h14486018", "tngc_h14528100", "tngc_h14579813",
        "tngc_h14859514", "tngc_h14940417", "tngc_h14985016", "tngc_h15031462",
        "tngc_h15087132", "tngc_h15125179", "tngc_h15172951", "tngc_h15214679",
        "tngc_h15264704", "tngc_h15304907", "tngc_h15348580", "tngc_h15386285",
        "tngc_h15428207", "tngc_h15465516", "tngc_h15500142", "tngc_h15543062",
    }
    if TNGC_TARGETS_JSON.is_file():
        targets = json.loads(TNGC_TARGETS_JSON.read_text())
        for t in targets[:136]:
            already_in_0.add(str(t["cluster_id"]))
    return already_in_0


SHARD0_TNGC_IDS = load_shard0_tngc_set()


def cluster_shard(cid: str, sim_kind: str) -> int:
    if sim_kind in ("SIMBA-100", "TNG300-1"):
        return 0
    return 0 if cid in SHARD0_TNGC_IDS else 1


def dataset_readme(repo: str, simba_ids: list[str], tng300_ids: list[str], tngc_ids: list[str], total_bytes: int) -> bytes:
    all_ids = simba_ids + tng300_ids + tngc_ids
    meta = (
        "---\n"
        "license: other\n"
        "license_name: illustristng-and-simba-data-terms\n"
        "license_link: https://www.tng-project.org/data/docs/background/#citation\n"
        f"pretty_name: Intracluster Medium (ICM) & Galaxy Cluster 3D + 12-Ion Sightline Atlas ({repo.split('/')[-1]})\n"
        "---\n\n"
    )
    body = f"""# Intracluster Medium (ICM) & Galaxy Cluster Atlas (`{repo}`)

Interactive 5-level 3D WebGL2 volumetric cubes ($\\pm 4\\,\\text{{Mpc}}$ down to $\\pm 15\\,\\text{{kpc}}$ BCG cores: `L0..L4` gas & velocity fields across 18 species + `S0..S4` stellar light in lossless WebP `tng50-viz/2` schema) and 120-ray 12-ion UV/EUV/X-ray Voigt absorption sightline libraries (`TNGS v2` binaries + Voigt component catalogs) for massive $z = 0$ galaxy clusters, powering **[https://icm.tanmaysingh.uk](https://icm.tanmaysingh.uk)** ([`tanmay-starslab/icm-atlas`](https://github.com/tanmay-starslab/icm-atlas)).

## Clusters Hosted in This Pack ({len(all_ids)} clusters, {total_bytes / 1e9:.2f} GB)

1. **`SIMBA-100` Massive Galaxy Clusters ($z = 0$, {len(simba_ids)} clusters, $\\pm 4\\,\\text{{Mpc}}$):**
   `{', '.join(simba_ids) if simba_ids else 'hosted in shard 0'}`
2. **`TNG300-1` Massive Galaxy Clusters & Rich Groups ($z = 0$, {len(tng300_ids)} clusters):**
   `{', '.join(tng300_ids) if tng300_ids else 'hosted in shard 0'}`
3. **`TNG-Cluster` Massive Zoom-In Galaxy Clusters ($z = 0$, {len(tngc_ids)} clusters, $\\pm 4\\,\\text{{Mpc}}$):**
   `{', '.join(tngc_ids)}`

## Data Terms & Citations

These derived visualization and absorption-line products are built from the public **TNG-Cluster / IllustrisTNG** data release (https://www.tng-project.org/data/; Nelson et al. 2024, *A&A* 686, A157; Nelson et al. 2019a) and the public **SIMBA** cosmological hydrodynamic simulation data release (http://simba.roe.ac.uk/; Davé et al. 2019, *MNRAS* 486, 2827).

## Code

MIT License — https://github.com/tanmay-starslab/icm-atlas
"""
    return (meta + body).encode("utf-8")


def collect_completed_clusters() -> list[tuple[str, Path, str]]:
    """Return [(cid, cluster_dir, sim_kind)] for all completed SIMBA-100, TNG300-1, and TNG-Cluster bundles."""
    out = []
    if SIMBA_ROOT.is_dir():
        for d in sorted(SIMBA_ROOT.iterdir()):
            if not d.is_dir() or not d.name.startswith("simba100_c"):
                continue
            if (d / "viz" / "manifest_v2.json").is_file() and (d / "web" / "catalog.json").is_file():
                out.append((d.name, d, "SIMBA-100"))
    if TNG300_ROOT.is_dir():
        for d in sorted(TNG300_ROOT.iterdir()):
            if not d.is_dir() or not d.name.startswith("tng300_sub"):
                continue
            if (d / "viz" / "manifest_v2.json").is_file() and (d / "web" / "catalog.json").is_file():
                out.append((d.name, d, "TNG300-1"))
    if TNGC_ROOT.is_dir():
        for d in sorted(TNGC_ROOT.iterdir()):
            if not d.is_dir() or not d.name.startswith("tngc_h"):
                continue
            if (d / "viz" / "manifest_v2.json").is_file() and (d / "web" / "catalog.json").is_file():
                out.append((d.name, d, "TNG-Cluster"))
    return out


def build_cluster_ops(cid: str, cdir: Path, tier: str = "webp") -> tuple[list[tuple[str, object, int]], list[tuple[str, object, int]]]:
    """Return (web_items, viz3d_items) where each item is (path_in_repo, Path|bytes, size)."""
    web_items = []
    viz3d_items = []
    pre = f"{cid}/"

    wdir = cdir / "web"
    vdir = cdir / "viz"

    # Public JSON metadata
    for name in ("galaxy.json", "catalog.json", "components.json"):
        p = wdir / name
        if not p.is_file():
            raise FileNotFoundError(f"{cid}: missing {p}")
        obj = json.loads(p.read_text(encoding="utf-8"))
        clean = U.strip_private(obj)
        b = (json.dumps(clean, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        web_items.append((pre + name, b, len(b)))
        if name == "galaxy.json":
            viz3d_items.append((pre + name, b, len(b)))

    # 120 sightline binaries
    bins = sorted((wdir / "s").glob("*.bin"))
    if not bins:
        raise FileNotFoundError(f"{cid}: no .bin files in {wdir / 's'}")
    for bp in bins:
        web_items.append((pre + "s/" + bp.name, bp, bp.stat().st_size))

    # 3D cubes & manifest_v2.json (filtered to lossless WebP tier so uploads are fast and compact)
    man = json.loads((vdir / "manifest_v2.json").read_text(encoding="utf-8"))
    if "galaxy" in man:
        man["galaxy"] = U.strip_private(man["galaxy"])
    for lk, lv in man.get("levels", {}).items():
        if lk.startswith("L"):
            VP.ALL_GAS_LEVELS[lk] = float(lv["half_kpc"])
            VP.GAS_LEVELS[lk] = float(lv["half_kpc"])
        elif lk.startswith("S"):
            VP.ALL_STAR_LEVELS[lk] = float(lv["half_kpc"])
            VP.STAR_LEVELS[lk] = float(lv["half_kpc"])
        if lv.get("r_mask_kpc") is None:
            VP.R_MASK_KPC.pop(lk, None)
        else:
            VP.R_MASK_KPC[lk] = float(lv["r_mask_kpc"])
    m_filtered = U.filter_manifest(man, tier)
    m_bytes = U._json_bytes(m_filtered)

    gz = U.TIERS[tier]["gz"]
    for _, _, _, cube in U.manifest_cubes(m_filtered):
        for rel, n in U.cube_files(cube, gz):
            p = vdir / rel
            if not p.is_file():
                raise FileNotFoundError(f"{cid}: missing cube {p}")
            web_items.append((pre + "viz/" + rel, p, n))
            viz3d_items.append((pre + "viz/" + rel, p, n))

    lut_p = vdir / "luts" / "luts.json"
    if lut_p.is_file():
        web_items.append((pre + "viz/luts/luts.json", lut_p, lut_p.stat().st_size))
        viz3d_items.append((pre + "viz/luts/luts.json", lut_p, lut_p.stat().st_size))

    web_items.append((pre + "viz/manifest_v2.json", m_bytes, len(m_bytes)))
    viz3d_items.append((pre + "viz/manifest_v2.json", m_bytes, len(m_bytes)))
    return web_items, viz3d_items


def upload_to_hf_repo(api: HfApi, repo: str, clusters: list[tuple[str, list[tuple[str, object, int]]]],
                      readme_bytes: bytes, batch_clusters: int = 8) -> None:
    t0 = time.time()
    V._call(api.create_repo, repo, repo_type="dataset", private=False, exist_ok=True)
    top_entries = list(V._call(api.list_repo_tree, repo, repo_type="dataset", recursive=False))
    existing_clusters = {x.path for x in top_entries if x.__class__.__name__ == "RepoFolder"}

    todo_clusters = []
    skipped_files = 0
    for cid, items in clusters:
        if cid in existing_clusters:
            skipped_files += len(items)
            continue
        c_ops = []
        c_bytes = 0
        for rel, src, sz in items:
            c_ops.append(CommitOperationAdd(path_in_repo=rel, path_or_fileobj=src if isinstance(src, bytes) else str(src)))
            c_bytes += sz
        if c_ops:
            todo_clusters.append((cid, c_ops, c_bytes))

    print(f"[{repo}] {skipped_files} files already up-to-date; {len(todo_clusters)}/{len(clusters)} clusters to upload.", flush=True)

    for i in range(0, len(todo_clusters), batch_clusters):
        batch = todo_clusters[i:i + batch_clusters]
        cids = [b[0] for b in batch]
        ops = [op for b in batch for op in b[1]]
        mb = sum(b[2] for b in batch) / 1e6
        t_c = time.time()
        print(f"[{repo}] Committing batch {i // batch_clusters + 1} ({', '.join(cids)}: {len(ops)} files, {mb:.1f} MB) ...", flush=True)
        V._call(
            api.create_commit,
            repo,
            ops,
            repo_type="dataset",
            commit_message=f"Upload ICM 5-level 3D + 120-ray cluster packs: {', '.join(cids)}",
        )
        print(f"[{repo}] Committed {', '.join(cids)} in {time.time() - t_c:.1f}s", flush=True)

    # Commit README.md
    V._call(
        api.create_commit,
        repo,
        [CommitOperationAdd(path_in_repo="README.md", path_or_fileobj=readme_bytes)],
        repo_type="dataset",
        commit_message=f"Update dataset card for {len(clusters)} ICM clusters",
    )
    print(f"[{repo}] Finished in {time.time() - t0:.1f}s!", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Upload completed ICM cluster packs to Hugging Face shards 0 and 1.")
    ap.add_argument("--batch-clusters", type=int, default=8, help="Clusters per Hugging Face commit (default: 8)")
    ap.add_argument("--shard", type=int, choices=(0, 1), default=None, help="Optional single shard to upload (0 or 1)")
    args = ap.parse_args()

    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
    token = V.read_token(Path("/scratch/tsingh65/cgm_work/cache/hf/token"))
    api = HfApi(token=token)

    completed = collect_completed_clusters()
    simba_all = [c[0] for c in completed if c[2] == "SIMBA-100"]
    tng300_all = [c[0] for c in completed if c[2] == "TNG300-1"]
    tngc_all = [c[0] for c in completed if c[2] == "TNG-Cluster"]
    print(
        f"Found {len(completed)} completed ICM cluster bundles: "
        f"{len(simba_all)} SIMBA-100 + {len(tng300_all)} TNG300-1 + {len(tngc_all)} TNG-Cluster",
        flush=True,
    )

    by_shard: dict[int, list[tuple[str, Path, str]]] = {0: [], 1: []}
    for cid, cdir, kind in completed:
        by_shard[cluster_shard(cid, kind)].append((cid, cdir, kind))

    shards_to_run = [args.shard] if args.shard is not None else [0, 1]
    for sh in shards_to_run:
        sh_clusters = by_shard[sh]
        if not sh_clusters:
            continue
        web_repo = WEB_REPOS[sh]
        viz_repo = VIZ3D_REPOS[sh]
        simba_ids = [c[0] for c in sh_clusters if c[2] == "SIMBA-100"]
        tng300_ids = [c[0] for c in sh_clusters if c[2] == "TNG300-1"]
        tngc_ids = [c[0] for c in sh_clusters if c[2] == "TNG-Cluster"]

        web_clusters = []
        viz3d_clusters = []
        total_web_bytes = 0
        total_viz_bytes = 0
        for cid, cdir, _kind in sh_clusters:
            w_items, v_items = build_cluster_ops(cid, cdir, tier="webp")
            web_clusters.append((cid, w_items))
            viz3d_clusters.append((cid, v_items))
            total_web_bytes += sum(x[2] for x in w_items)
            total_viz_bytes += sum(x[2] for x in v_items)

        print(f"Planned shard {sh} -> {web_repo}: {len(web_clusters)} clusters, {total_web_bytes / 1e9:.2f} GB", flush=True)
        print(f"Planned shard {sh} -> {viz_repo}: {len(viz3d_clusters)} clusters, {total_viz_bytes / 1e9:.2f} GB", flush=True)

        web_readme = dataset_readme(web_repo, simba_ids, tng300_ids, tngc_ids, total_web_bytes)
        viz_readme = dataset_readme(viz_repo, simba_ids, tng300_ids, tngc_ids, total_viz_bytes)

        upload_to_hf_repo(api, web_repo, web_clusters, web_readme, batch_clusters=args.batch_clusters)
        upload_to_hf_repo(api, viz_repo, viz3d_clusters, viz_readme, batch_clusters=args.batch_clusters)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
