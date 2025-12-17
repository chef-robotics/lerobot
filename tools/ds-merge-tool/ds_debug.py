from pathlib import Path
import json
import pyarrow.parquet as pq  # or pandas, whichever you have
from datasets import load_dataset

root = Path("/home/inkyu/workspace/dataset/sandi/lettuce-sandwich-181eps-5p2/")

ep_idx = 171
ep_name = f"episode_{ep_idx:06d}"

parquet_path = root / "data" / "chunk-000" / f"{ep_name}.parquet"
episodes_jsonl = root / "meta" / "episodes.jsonl"
cam_high_path = root / "videos" / "chunk-000" / "observation.images.cam_high" / f"{ep_name}.mp4"

print("Parquet:", parquet_path.exists(), parquet_path)
print("Video:", cam_high_path.exists(), cam_high_path)

# 0) Load the full HF dataset so we can inspect episode_index values
data_dir = root / "data"
ds = load_dataset("parquet", data_dir=str(data_dir), split="train")

print("\n=== Global episode_index stats from parquet ===")
print("min episode_index:", min(ds["episode_index"]))
print("max episode_index:", max(ds["episode_index"]))

unique_eps = sorted(set(ds["episode_index"]))
print("Last 20 unique episode_index values:", unique_eps[-20:])

# 1) Number of observation frames in this specific episode parquet
print("\n=== Episode-level checks (episode_index =", ep_idx, ") ===")
table = pq.read_table(parquet_path)
num_obs = table.num_rows
print("num_obs (rows in parquet):", num_obs)

# 2) length field from episodes.jsonl
length_val = None
with episodes_jsonl.open("r") as f:
    for line in f:
        obj = json.loads(line)
        if obj.get("episode_index") == ep_idx:
            length_val = obj.get("length")
            break
print("length from episodes.jsonl:", length_val)

# 3) Optional: count video frames via OpenCV (if installed)
try:
    import cv2
    cap = cv2.VideoCapture(str(cam_high_path))
    num_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    print("num_frames (cam_high):", num_frames)
except Exception as e:
    print("Could not read video frames:", e)
