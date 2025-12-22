import argparse
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set

import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm
import yaml


def ensure_dirs(root: Path):
    (root / "data" / "chunk-000").mkdir(parents=True, exist_ok=True)
    (root / "videos" / "chunk-000").mkdir(parents=True, exist_ok=True)


def list_episode_indices(data_chunk_dir: Path) -> List[int]:
    """Return sorted list of episode indices (ints) for episode_XXXXXX.parquet."""
    indices = []
    for p in data_chunk_dir.glob("episode_*.parquet"):
        stem = p.stem  # episode_000000
        idx = int(stem.split("_")[-1])
        indices.append(idx)
    return sorted(indices)


def apply_selection(
    ep_indices: List[int],
    include: Optional[List[int]] = None,
    include_ranges: Optional[List[Tuple[int, int]]] = None,
    exclude: Optional[List[int]] = None,
    exclude_ranges: Optional[List[Tuple[int, int]]] = None,
) -> List[int]:
    """
    Filter ep_indices using include/exclude lists and ranges.
    - include / include_ranges: if provided, keep ONLY those.
    - exclude / exclude_ranges: remove those from the result.
    Ranges are [start, end) (end is exclusive).
    """
    ep_set = set(ep_indices)

    # --- handle include (intersection) ---
    if include is not None or include_ranges is not None:
        include_set = set()
        if include is not None:
            include_set.update(include)
        if include_ranges is not None:
            for start, end in include_ranges:
                include_set.update(range(start, end))
        ep_set = ep_set.intersection(include_set)

    # --- handle exclude (subtraction) ---
    if exclude is not None:
        ep_set.difference_update(exclude)
    if exclude_ranges is not None:
        for start, end in exclude_ranges:
            ep_set.difference_update(range(start, end))

    return sorted(ep_set)


def copy_single_episode_with_reindex(
    src_root: Path,
    dst_root: Path,
    old_idx: int,
    new_idx: int,
    global_frame_offset: int,
    new_task_index: Optional[int] = None,
) -> int:
    """
    Copy ONE episode's parquet + all camera videos from src_root to dst_root,
    renaming and rewriting the parquet so that:
      - episode_index == new_idx for all rows
      - frame_index == 0..(len-1) within that episode
      - index is global, starting at global_frame_offset
      - task_index is updated to new_task_index (if provided)

    Returns:
        episode_length (number of rows) so the caller can update global_frame_offset.
    """
    # --- Paths ---
    src_data = src_root / "data" / "chunk-000"
    dst_data = dst_root / "data" / "chunk-000"

    src_video_chunk = src_root / "videos" / "chunk-000"
    dst_video_chunk = dst_root / "videos" / "chunk-000"

    old_name = f"episode_{old_idx:06d}"
    new_name = f"episode_{new_idx:06d}"

    src_parquet = src_data / f"{old_name}.parquet"
    dst_parquet = dst_data / f"{new_name}.parquet"
    dst_parquet.parent.mkdir(parents=True, exist_ok=True)

    if not src_parquet.exists():
        raise FileNotFoundError(f"Missing parquet file: {src_parquet}")

    # --- Read original parquet ---
    table = pq.read_table(src_parquet)
    num_rows = table.num_rows

    # --- Build new columns for episode_index, frame_index, index ---
    column_data = {}
    schema = table.schema

    for col_name in table.column_names:
        field_type = schema.field(col_name).type
        if col_name == "episode_index":
            # All rows belong to remapped global episode index
            arr = pa.array([new_idx] * num_rows, type=field_type)
            column_data[col_name] = arr
        elif col_name == "frame_index":
            # Frame index within episode: 0..num_rows-1
            arr = pa.array(range(num_rows), type=field_type)
            column_data[col_name] = arr
        elif col_name == "index":
            # Global index across entire merged dataset
            arr = pa.array(range(global_frame_offset, global_frame_offset + num_rows), type=field_type)
            column_data[col_name] = arr
        elif col_name == "task_index" and new_task_index is not None:
             # Remap task index
            arr = pa.array([new_task_index] * num_rows, type=field_type)
            column_data[col_name] = arr
        else:
            # Keep original data
            column_data[col_name] = table[col_name]

    new_table = pa.table(column_data)

    # --- Write reindexed parquet to destination ---
    pq.write_table(new_table, dst_parquet)

    # --- Copy videos for all cameras (if they exist) ---
    if src_video_chunk.exists():
        for cam_dir in src_video_chunk.iterdir():
            if not cam_dir.is_dir():
                continue
            rel_cam = cam_dir.name
            src_mp4 = cam_dir / f"{old_name}.mp4"
            if not src_mp4.exists():
                # some episodes might be missing a camera; skip that camera
                continue
            dst_cam_dir = dst_video_chunk / rel_cam
            dst_cam_dir.mkdir(parents=True, exist_ok=True)
            dst_mp4 = dst_cam_dir / f"{new_name}.mp4"
            shutil.copy2(src_mp4, dst_mp4)

    return num_rows


def remap_jsonl(
    src_path: Path,
    dst_path: Path,
    index_map: Dict[int, int],
    keys_to_remap=("episode_index",),
):
    """
    Read JSONL, remap any integer fields named in keys_to_remap using index_map,
    and append to dst_path.

    For per-episode files (episodes.jsonl, episodes_stats.jsonl, tasks.jsonl):
    - We only keep objects whose old index is in index_map.
    - We rewrite the index to the new global index.
    - Objects without those keys are kept as-is (global stats, etc.).
    """
    if not src_path.exists():
        return

    # Load entire file once
    records = []
    with src_path.open("r") as f_in:
        for line in f_in:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with dst_path.open("a") as f_out:
        for obj in records:
            # Check if this object has any of the keys_to_remap
            has_index_key = False
            drop_line = False

            for k in keys_to_remap:
                if k in obj:
                    has_index_key = True
                    old_idx = obj[k]
                    if old_idx not in index_map:
                        # Episode was filtered out; skip this object
                        drop_line = True
                        break
                    # Remap to new index
                    obj[k] = index_map[old_idx]

            if drop_line:
                continue

            # Keep:
            # - per-episode objects whose index we remapped
            # - or global objects with no episode_index-like key
            f_out.write(json.dumps(obj) + "\n")


def merge_info_json(
    template_info_path: Path,
    episodes_path: Path,
    tasks_path: Path,
    total_episodes: int,
    out_path: Path,
):
    """
    Build a correct merged info.json:

    - Use `template_info_path` (info.json from the first dataset) as a template
      for static fields (codebase_version, robot_type, features, etc.).
    - Recompute:
        * total_episodes
        * total_frames  (sum of `length` in merged episodes.jsonl)
        * total_tasks   (number of lines in tasks.jsonl)
        * total_videos  (total_episodes * number of video cameras)
        * splits["train"] = f"0:{total_episodes}"
    """
    if not template_info_path.exists():
        raise FileNotFoundError(f"Template info.json not found: {template_info_path}")

    with template_info_path.open("r") as f:
        merged = json.load(f)

    # ---- total_episodes ----
    merged["total_episodes"] = int(total_episodes)

    # ---- total_frames: sum of length from merged episodes.jsonl ----
    total_frames = 0
    if episodes_path.exists():
        with episodes_path.open("r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if "length" in obj:
                    total_frames += int(obj["length"])
    merged["total_frames"] = int(total_frames)

    # ---- total_tasks: count lines in merged tasks.jsonl ----
    total_tasks = 0
    if tasks_path.exists():
        with tasks_path.open("r") as f:
            for line in f:
                if line.strip():
                    total_tasks += 1
    merged["total_tasks"] = int(total_tasks)

    # ---- total_videos: total_episodes * number of video cameras ----
    num_cams = 0
    features = merged.get("features", {})
    for feat_name, feat_info in features.items():
        if isinstance(feat_info, dict) and feat_info.get("dtype") == "video":
            num_cams += 1
    merged["total_videos"] = int(total_episodes * num_cams)

    # ---- splits ----
    splits = merged.get("splits", {})
    splits["train"] = f"0:{total_episodes}"
    merged["splits"] = splits

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(merged, f, indent=2)

    print(
        f"Written merged info.json with {total_episodes} episodes, "
        f"{total_frames} frames, {total_tasks} tasks, {merged['total_videos']} videos to {out_path}"
    )


def load_dataset_selection_from_yaml(
    config_path: Optional[Path],
    input_roots: List[Path],
) -> Dict[str, Dict]:
    """
    Load DATASET_SELECTION from a YAML file, falling back to {} (take all)
    for any dataset not specified in the config, to match original behavior.
    """
    selection: Dict[str, Dict] = {str(p.resolve()): {} for p in input_roots}

    if config_path is None:
        return selection

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r") as f:
        data = yaml.safe_load(f) or {}

    # YAML should map absolute-path-string -> {include/include_ranges/...}
    for k, v in data.items():
        selection[str(Path(k).resolve())] = v or {}

    return selection


def parse_args():
    parser = argparse.ArgumentParser(
        description="Merge episodic parquet+video datasets with per-dataset filters.",
    )

    parser.add_argument(
        "--input",
        type=str,
        action="append",
        required=True,
        help="Path to input dataset root (can be used multiple times).",
    )

    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to output merged dataset root.",
    )

    parser.add_argument(
        "--config",
        type=str,
        help=(
            "Optional YAML config file for per-dataset selection. "
            "Keys: absolute dataset paths; values: dict with optional "
            "include, include_ranges, exclude, exclude_ranges."
        ),
    )

    return parser.parse_args()


def load_tasks_from_episodes(episodes_path: Path) -> Dict[int, str]:
    """Load episode_index -> task_string map from episodes.jsonl"""
    ep_tasks = {}
    if not episodes_path.exists():
        return ep_tasks
    
    with episodes_path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line: 
                continue
            obj = json.loads(line)
            # Assuming single task or taking the first one
            tasks = obj.get("tasks", [])
            if isinstance(tasks, str):
                tasks = [tasks]
            if tasks:
                ep_tasks[obj["episode_index"]] = tasks[0]
    return ep_tasks


def main():
    args = parse_args()

    input_roots = [Path(p).expanduser().resolve() for p in args.input]
    output_root = Path(args.output).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve() if args.config else None

    print("Input datasets:")
    for p in input_roots:
        print("  -", p)

    print("Output dataset:")
    print("  -", output_root)

    if config_path:
        print(f"Using YAML config: {config_path}")

    DATASET_SELECTION = load_dataset_selection_from_yaml(config_path, input_roots)

    ensure_dirs(output_root)

    # Global counters across ALL merged datasets
    global_next_episode_idx = 0
    global_next_frame_index = 0

    info_paths: List[Path] = []

    # Paths for merged meta
    merged_meta = output_root / "meta"
    merged_episodes_jsonl = merged_meta / "episodes.jsonl"
    merged_episodes_stats_jsonl = merged_meta / "episodes_stats.jsonl"
    merged_tasks_jsonl = merged_meta / "tasks.jsonl"

    # Clear any existing meta files if re-running
    for p in [merged_episodes_jsonl, merged_episodes_stats_jsonl, merged_tasks_jsonl]:
        if p.exists():
            p.unlink()

    # --- Pre-scan to build global task map ---
    print("\nPre-scanning tasks to build global registry...")
    unique_tasks_order = []
    unique_tasks_set = set()
    
    # Store selected episodes for the second pass
    # Structure: [ (src_root, [list of selected old_indices]) ]
    datasets_plan = [] 

    for src_root in input_roots:
        src_root = src_root.resolve()
        data_chunk_dir = src_root / "data" / "chunk-000"
        
        # 1. Determine selected episodes
        ep_indices = list_episode_indices(data_chunk_dir)
        cfg = DATASET_SELECTION.get(str(src_root), {})
        ep_indices = apply_selection(
            ep_indices,
            include=cfg.get("include"),
            include_ranges=cfg.get("include_ranges"),
            exclude=cfg.get("exclude"),
            exclude_ranges=cfg.get("exclude_ranges"),
        )
        datasets_plan.append((src_root, ep_indices))
        
        if not ep_indices:
            continue
            
        # 2. Load episode tasks
        ep_tasks_map = load_tasks_from_episodes(src_root / "meta" / "episodes.jsonl")
        
        # 3. Collect unique tasks in order of appearance
        for ep_idx in ep_indices:
            t_str = ep_tasks_map.get(ep_idx)
            if t_str and t_str not in unique_tasks_set:
                unique_tasks_set.add(t_str)
                unique_tasks_order.append(t_str)

    # Build task string -> new index map
    task_str_to_id = {t: i for i, t in enumerate(unique_tasks_order)}
    print(f"Found {len(task_str_to_id)} unique tasks.")

    # Write merged tasks.jsonl IMMEDIATELY
    merged_tasks_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with merged_tasks_jsonl.open("w") as f:
        for t_str, t_id in task_str_to_id.items():
            f.write(json.dumps({"task_index": t_id, "task": t_str}) + "\n")

    # --- Process each input dataset (Second Pass) ---
    for src_root, ep_indices in datasets_plan:
        print(f"\nProcessing {src_root}")
        
        if not ep_indices:
            print(f"  No episodes selected for {src_root}, skipping.")
            continue

        print(
            f"[DEBUG] {src_root.name}: processing {len(ep_indices)} selected episodes"
        )
        
        # Load tasks map for this dataset again to look up during copy
        ep_tasks_map = load_tasks_from_episodes(src_root / "meta" / "episodes.jsonl")

        # Mapping: old local episode index -> new global episode index
        index_map: Dict[int, int] = {}

        # Copy & reindex each episode
        for old_idx in tqdm(
            ep_indices,
            total=len(ep_indices),
            desc=f"Episodes ({src_root.name})",
            leave=False,
        ):
            new_idx = global_next_episode_idx
            index_map[old_idx] = new_idx
            
            # Determine new task index
            t_str = ep_tasks_map.get(old_idx)
            new_task_idx = task_str_to_id.get(t_str) if t_str else 0 # Default to 0 if missing?

            # This updates the parquet columns and copies videos
            episode_length = copy_single_episode_with_reindex(
                src_root=src_root,
                dst_root=output_root,
                old_idx=old_idx,
                new_idx=new_idx,
                global_frame_offset=global_next_frame_index,
                new_task_index=new_task_idx,
            )

            global_next_frame_index += episode_length
            global_next_episode_idx += 1

        # Remap meta JSONLs
        src_meta = src_root / "meta"
        remap_jsonl(
            src_meta / "episodes.jsonl",
            merged_episodes_jsonl,
            index_map,
            keys_to_remap=("episode_index",),
        )
        remap_jsonl(
            src_meta / "episodes_stats.jsonl",
            merged_episodes_stats_jsonl,
            index_map,
            keys_to_remap=("episode_index",),
        )

        # Keep info.json for later merge
        info_paths.append(src_meta / "info.json")

    # Use the first info.json as template for static fields
    if not info_paths:
        raise RuntimeError("No info.json files found in input datasets; cannot build merged info.json.")
    template_info = info_paths[0]

    # Build a correct merged info.json
    merge_info_json(
        template_info_path=template_info,
        episodes_path=merged_episodes_jsonl,
        tasks_path=merged_tasks_jsonl,
        total_episodes=global_next_episode_idx,
        out_path=output_root / "meta" / "info.json",
    )

    print(f"\nDone. Merged {global_next_episode_idx} episodes into {output_root}")
    print(f"Total frames (from episode lengths) ≈ {global_next_frame_index}")


if __name__ == "__main__":
    main()
