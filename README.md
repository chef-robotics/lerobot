# trossen-lerobot (Chef Fork)

Private fork of [Interbotix/lerobot](https://github.com/Interbotix/lerobot) for the SANDI legacy (v2) workflow.

## Upstream Documentation

For general usage, see:
- [Trossen LeRobot Documentation](https://docs.trossenrobotics.com/trossen_arm/main/tutorials/lerobot.html)
- [Upstream README](./UPSTREAM_README.md)

This README covers Chef-specific information.

## Workflow Context

This repo is part of the **legacy v2 workflow**:

| Workflow | Dataset Format | Repos |
|----------|---------------|-------|
| **New (v3)** | LeRobotDataset v3 | chef-lerobot + chef-lerobot_trossen |
| **Legacy (v2)** | LeRobotDataset v2.1 | **trossen-lerobot** + openpi |

Use this repo when:
- Working with existing v2.1 format datasets
- Using OpenPI for training/inference
- Following Trossen's official documentation

## Branch Structure

| Branch | Purpose |
|--------|---------|
| `trossen-ai` | **Working branch** - Chef development |
| Other branches | Feature branches (sherry/*, etc.) |

## Chef Modifications

- Dataset labeling and query scripts (#2)
- Training script improvements for ACT (#1)
- Control root directory fixes
- `.tags` gitignore

## Setup

This repo has its own virtual environment (separate from the main sandi/ workspace):

```bash
cd ChefResearch/sandi/third_party/trossen-lerobot
uv sync
source .venv/bin/activate
```

## Common Commands

### Recording Episodes

```bash
python lerobot/scripts/control_robot.py record \
    --robot-path lerobot/configs/robot/trossen_ai.yaml \
    --fps 30 \
    --repo-id ${HF_USER}/my-dataset \
    --num-episodes 10 \
    --episode-time-s 60
```

### Training

```bash
python lerobot/scripts/train.py \
    policy=act \
    env=trossen_ai \
    dataset_repo_id=${HF_USER}/my-dataset
```

### Visualization

```bash
python lerobot/scripts/visualize_dataset.py \
    --repo-id ${HF_USER}/my-dataset
```

See [Trossen documentation](https://docs.trossenrobotics.com/trossen_arm/main/tutorials/lerobot.html) for detailed instructions.

## Development Workflow

### Making Changes

```bash
git checkout trossen-ai
# ... make changes ...
git add . && git commit -m "Description"
git push origin trossen-ai
```

### Update Parent Repo

```bash
cd ../..  # to sandi/
git add third_party/trossen-lerobot
git commit -m "Update trossen-lerobot submodule"
```

### Syncing with Upstream

```bash
git remote add upstream https://github.com/Interbotix/lerobot.git
git fetch upstream
git checkout trossen-ai
git merge upstream/trossen-ai  # or appropriate branch
git push origin trossen-ai
```

## Integration with OpenPI

This repo provides datasets for OpenPI training:

1. **Record episodes** using trossen-lerobot
2. **Upload to HuggingFace Hub**
3. **Train with OpenPI** using the dataset repo_id

See `../openpi/examples/trossen_ai/README.md` for the full workflow.

## Key Directories

```
trossen-lerobot/
├── lerobot/
│   ├── common/
│   │   ├── policies/           # ACT, diffusion, pi0, etc.
│   │   └── robot_devices/      # Trossen AI hardware
│   ├── configs/                # YAML configs
│   └── scripts/
│       ├── control_robot.py    # Recording/teleoperation
│       ├── train.py            # Training
│       └── eval.py             # Evaluation
└── examples/
    └── 12_use_trossen_ai.md    # Trossen AI tutorial
```

## Dataset Format (v2.1)

```
dataset/
├── data/
│   └── chunk-000/
│       └── episode_*.parquet
├── videos/
│   └── chunk-000/
│       └── <camera_name>/
│           └── episode_*.mp4
└── meta/
    ├── info.json
    ├── episodes.jsonl
    └── episodes_stats.jsonl
```

## Related Submodules

- **openpi**: Used with this repo for training/inference
- **chef-lerobot**: New v3 workflow (separate, not used with this)
- **chef-lerobot_trossen**: New v3 workflow (separate, not used with this)
