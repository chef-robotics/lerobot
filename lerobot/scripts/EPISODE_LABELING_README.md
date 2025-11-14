# Episode Labeling Tool for LeRobot Datasets

This toolset allows you to add custom metadata labels to episodes in your LeRobot datasets by playing back the videos and interactively labeling them.

## Scripts

1. **`label_episodes.py`** - Interactive labeling tool
2. **`query_episode_metadata.py`** - Query and filter labeled episodes

## Installation

Make sure you have the required dependencies:

```bash
pip install opencv-python jsonlines torch numpy
```

## Usage

### 1. Label Episodes

The main script plays videos from your dataset and prompts you to add metadata labels.

**Basic usage:**

```bash
python label_episodes.py \
    --repo-id TrossenRoboticsCommunity/trossen_ai_stationary_handover_cube \
    --root sandi/datasets/TrossenRoboticsCommunity/trossen_ai_stationary_handover_cube \
    --camera observation.images.top \
    --metadata-keys right_arm_helping cube_dropped grasp_quality
```

**Options:**

- `--repo-id`: The repository ID of your dataset
- `--root`: Root directory where the dataset is stored
- `--camera`: Which camera view to display (e.g., `observation.images.top`)
- `--metadata-keys`: List of metadata keys you want to label (space-separated)
- `--output`: (Optional) Custom output file path (default: `<root>/meta/episodes_metadata.jsonl`)
- `--start-episode`: (Optional) Start from a specific episode index (default: 0)
- `--episodes`: (Optional) Label only specific episodes (e.g., `--episodes 0 5 10`)

**Interactive controls:**

While watching video:
- **`q`** - Finish watching and proceed to labeling
- **`r`** - Replay from beginning
- **`SPACE`** - Pause/resume playback

When entering metadata:
- **Boolean values**: Enter `true`, `false`, `t`, `f`, `yes`, `no`, `1`, or `0`
- **Numbers**: Enter numeric values (integers or floats)
- **Strings**: Enter any text
- **Skip**: Press Enter to skip a metadata key

**Output:**

Metadata is saved to `<dataset_root>/meta/episodes_metadata.jsonl` in the format:

```json
{"episode_index": 0, "right_arm_helping": true, "cube_dropped": false, "grasp_quality": 8}
{"episode_index": 1, "right_arm_helping": false, "cube_dropped": false, "grasp_quality": 9}
{"episode_index": 2, "right_arm_helping": true, "cube_dropped": true, "grasp_quality": 3}
```

### 2. Query Metadata

Use this script to view and filter episodes based on their metadata.

**Show all metadata:**

```bash
python query_episode_metadata.py \
    --metadata-file sandi/datasets/.../meta/episodes_metadata.jsonl
```

**Filter by conditions:**

```bash
# Find episodes where right arm was helping
python query_episode_metadata.py \
    --metadata-file ... \
    --filter right_arm_helping=true

# Find episodes with multiple conditions
python query_episode_metadata.py \
    --metadata-file ... \
    --filter right_arm_helping=true grasp_quality=9
```

**Show statistics:**

```bash
python query_episode_metadata.py \
    --metadata-file ... \
    --stats
```

**Export filtered episode indices:**

```bash
python query_episode_metadata.py \
    --metadata-file ... \
    --filter right_arm_helping=true \
    --export-indices filtered_episodes.json
```

This creates a JSON file with episode indices that you can use to filter your dataset:

```python
import json
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset

# Load filtered episode indices
with open("filtered_episodes.json") as f:
    episodes = json.load(f)

# Load dataset with only those episodes
dataset = LeRobotDataset(
    repo_id="your/dataset",
    root="path/to/dataset",
    episodes=episodes  # Only load filtered episodes
)
```

## Example Workflow

```bash
# Step 1: Label your episodes
python label_episodes.py \
    --repo-id TrossenRoboticsCommunity/trossen_ai_stationary_handover_cube \
    --root sandi/datasets/TrossenRoboticsCommunity/trossen_ai_stationary_handover_cube \
    --camera observation.images.top \
    --metadata-keys right_arm_helping successful_handover

# Step 2: View statistics
python query_episode_metadata.py \
    --metadata-file sandi/datasets/.../meta/episodes_metadata.jsonl \
    --stats

# Step 3: Filter and export successful episodes
python query_episode_metadata.py \
    --metadata-file sandi/datasets/.../meta/episodes_metadata.jsonl \
    --filter successful_handover=true \
    --export-indices successful_episodes.json

# Step 4: Use filtered episodes in your training code
# (see Python example above)
```

## Tips

1. **Resume labeling**: The script automatically saves progress. If you stop and restart, it will ask if you want to overwrite existing labels.

2. **Find available cameras**: Check which cameras are available in your dataset:
   ```python
   from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
   dataset = LeRobotDataset(repo_id="...", root="...")
   print(dataset.meta.camera_keys)
   ```

3. **Batch labeling**: If you want to label only specific episodes, use the `--episodes` flag:
   ```bash
   python label_episodes.py ... --episodes 0 1 2 5 10
   ```

4. **Metadata file location**: By default, metadata is saved to `<dataset_root>/meta/episodes_metadata.jsonl`. This keeps it with your dataset but separate from the standard LeRobot files.

## Integrating Metadata into Your Training Pipeline

Once you've labeled episodes, you can use the metadata in your training:

```python
import json
from pathlib import Path
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset

# Load metadata
metadata_file = Path("sandi/datasets/.../meta/episodes_metadata.jsonl")
import jsonlines
episode_metadata = {}
with jsonlines.open(metadata_file) as reader:
    for entry in reader:
        episode_metadata[entry["episode_index"]] = entry

# Filter episodes based on metadata
good_episodes = [
    ep_idx for ep_idx, meta in episode_metadata.items()
    if meta.get("successful_handover") == True
]

# Load dataset with filtered episodes
dataset = LeRobotDataset(
    repo_id="your/dataset",
    root="path/to/dataset",
    episodes=good_episodes
)

# Use in training...
```

## Troubleshooting

**Issue**: Video playback is too fast/slow
- Adjust the FPS in the `_play_episode` method or use the pause/replay controls

**Issue**: Camera key not found
- Run this to see available cameras:
  ```python
  from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
  ds = LeRobotDataset(repo_id="...", root="...")
  print(ds.meta.camera_keys)
  ```

**Issue**: Videos won't play
- Make sure OpenCV is installed: `pip install opencv-python`
- Ensure videos are downloaded: The script sets `download_videos=True` by default

