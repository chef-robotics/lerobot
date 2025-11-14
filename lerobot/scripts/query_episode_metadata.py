#!/usr/bin/env python3
"""
Script to query and filter episodes based on custom metadata.

Usage:
    python query_episode_metadata.py --metadata-file <path> [--filter key=value]

Examples:
    # Show all metadata
    python query_episode_metadata.py --metadata-file sandi/datasets/.../meta/episodes_metadata.jsonl
    
    # Filter by specific value
    python query_episode_metadata.py --metadata-file ... --filter right_arm_helping=true
    
    # Filter by multiple conditions
    python query_episode_metadata.py --metadata-file ... --filter right_arm_helping=true cube_color=red
"""

import argparse
import json
from pathlib import Path

import jsonlines


def parse_filter_value(value_str: str):
    """Parse string value to appropriate Python type."""
    value_lower = value_str.lower()
    
    # Boolean
    if value_lower in ['true', 't', 'yes', '1']:
        return True
    elif value_lower in ['false', 'f', 'no', '0']:
        return False
    
    # Number
    try:
        if '.' in value_str:
            return float(value_str)
        else:
            return int(value_str)
    except ValueError:
        # String
        return value_str


def load_metadata(metadata_file: Path) -> list[dict]:
    """Load all metadata entries."""
    if not metadata_file.exists():
        print(f"Error: Metadata file not found: {metadata_file}")
        return []
    
    entries = []
    with jsonlines.open(metadata_file, "r") as reader:
        for entry in reader:
            entries.append(entry)
    
    return sorted(entries, key=lambda x: x["episode_index"])


def filter_metadata(entries: list[dict], filters: dict) -> list[dict]:
    """Filter metadata entries based on key-value pairs."""
    if not filters:
        return entries
    
    filtered = []
    for entry in entries:
        match = True
        for key, value in filters.items():
            if key not in entry or entry[key] != value:
                match = False
                break
        if match:
            filtered.append(entry)
    
    return filtered


def print_metadata(entries: list[dict], show_details: bool = True):
    """Pretty print metadata entries."""
    if not entries:
        print("No entries found.")
        return
    
    print(f"\nFound {len(entries)} episode(s):")
    print("=" * 80)
    
    # Collect all unique keys
    all_keys = set()
    for entry in entries:
        all_keys.update(entry.keys())
    all_keys.discard("episode_index")
    all_keys = sorted(all_keys)
    
    for entry in entries:
        print(f"\nEpisode {entry['episode_index']}:")
        if show_details:
            for key in all_keys:
                if key in entry:
                    value = entry[key]
                    value_type = type(value).__name__
                    print(f"  {key}: {value} ({value_type})")
        else:
            # Compact view
            metadata_str = ", ".join(f"{k}={entry[k]}" for k in all_keys if k in entry)
            print(f"  {metadata_str}")
    
    print("=" * 80)


def export_episode_indices(entries: list[dict], output_file: Path):
    """Export episode indices to a file (useful for filtering datasets)."""
    indices = [entry["episode_index"] for entry in entries]
    
    with open(output_file, "w") as f:
        json.dump(indices, f, indent=2)
    
    print(f"\nExported {len(indices)} episode indices to: {output_file}")


def print_statistics(entries: list[dict]):
    """Print statistics about metadata."""
    if not entries:
        print("No entries to analyze.")
        return
    
    # Collect all keys
    all_keys = set()
    for entry in entries:
        all_keys.update(entry.keys())
    all_keys.discard("episode_index")
    
    print("\n" + "=" * 80)
    print("Metadata Statistics")
    print("=" * 80)
    print(f"Total episodes: {len(entries)}")
    print(f"Metadata keys: {', '.join(sorted(all_keys))}")
    
    # For each key, show value distribution
    for key in sorted(all_keys):
        values = [entry[key] for entry in entries if key in entry]
        if not values:
            continue
        
        print(f"\n{key}:")
        print(f"  Total: {len(values)}/{len(entries)} episodes")
        
        # Count value frequencies
        if isinstance(values[0], bool) or len(set(values)) < 20:
            from collections import Counter
            counts = Counter(values)
            for value, count in counts.most_common():
                percentage = (count / len(values)) * 100
                print(f"    {value}: {count} ({percentage:.1f}%)")
        else:
            # Numeric statistics
            try:
                import numpy as np
                values_array = np.array(values)
                print(f"    min: {values_array.min()}")
                print(f"    max: {values_array.max()}")
                print(f"    mean: {values_array.mean():.2f}")
                print(f"    std: {values_array.std():.2f}")
            except:
                print(f"    (mixed types or non-numeric)")
    
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Query episode metadata")
    parser.add_argument(
        "--metadata-file",
        type=str,
        required=True,
        help="Path to episodes_metadata.jsonl file"
    )
    parser.add_argument(
        "--filter",
        nargs="+",
        default=[],
        help="Filter by key=value pairs (e.g., 'right_arm_helping=true' 'cube_color=red')"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics about metadata"
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Use compact view for output"
    )
    parser.add_argument(
        "--export-indices",
        type=str,
        default=None,
        help="Export filtered episode indices to JSON file"
    )
    
    args = parser.parse_args()
    
    # Load metadata
    metadata_file = Path(args.metadata_file)
    entries = load_metadata(metadata_file)
    
    if not entries:
        return
    
    print(f"Loaded {len(entries)} metadata entries from {metadata_file}")
    
    # Parse filters
    filters = {}
    for filter_str in args.filter:
        if "=" not in filter_str:
            print(f"Warning: Invalid filter format '{filter_str}', expected 'key=value'")
            continue
        
        key, value_str = filter_str.split("=", 1)
        key = key.strip()
        value = parse_filter_value(value_str.strip())
        filters[key] = value
    
    if filters:
        print(f"Applying filters: {filters}")
        entries = filter_metadata(entries, filters)
    
    # Print results
    if args.stats:
        print_statistics(entries)
    else:
        print_metadata(entries, show_details=not args.compact)
    
    # Export if requested
    if args.export_indices:
        export_episode_indices(entries, Path(args.export_indices))


if __name__ == "__main__":
    main()

