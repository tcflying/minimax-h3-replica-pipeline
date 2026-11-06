# Submit one segment through the external-groups (EG) Director pipeline to a running
# ComfyUI on 127.0.0.1:8193.  Edit the constants, then:  python generate_segment.py
import ipaddress
import json
import time
import urllib.error
import urllib.parse
import urllib.request

COMFY_HOST = "127.0.0.1"          # fixed loopback ComfyUI instance
COMFY_PORT = 8193
WORKFLOW = "workflows/api-template-eg-seg.json"   # this repo's template
INPUT_MP4 = "seg06.mp4"          # your 24fps source window, placed in ComfyUI input/
PICTURE1 = "p3-original.jpg"     # product reference image in input/
PICTURE2 = "p3-motif.png"        # pattern crop in input/
WIDTH, HEIGHT, FRAMES = 540, 960, 124   # 32-multiple canvas, 17k+5 frame grid
SEED = 20261106
PROMPT = (
    "Keep the subjects, scene, camera and every motion exactly as in <Video 1>. "
    "The shoes in the video become the pink knit sock-shoes from <Picture 1>: "
    "light-pink ribbed cuff, rounded pink toe, gray heel pull-loop, white pattern "
    "rows of triangles and dots (see <Picture 2>). "
    "An off-screen female voice says warmly: \"Now watch: a walk, a squat, a turn.\" "
    "- nobody on screen speaks, lips stay closed. Ambient: soft kitchen room tone. "
    "Light playful background music at low volume."
)


def safe_url(path: str) -> str:
    """Fixed-scheme loopback URL only; any other target is rejected."""
    url = "http://%s:%d%s" % (COMFY_HOST, COMFY_PORT, path)
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname != COMFY_HOST or parsed.port != COMFY_PORT:
        raise ValueError("blocked non-local target")
    if not ipaddress.ip_address(parsed.hostname).is_loopback:
        raise ValueError("blocked non-loopback IP")
    return url


def main() -> None:
    wf = json.load(open(WORKFLOW, encoding="utf-8"))
    p = wf["prompt"]
    # attention backend: 23x speedup measured vs pytorch cross-attention on a 3090
    p["50"] = {"class_type": "ModelAttentionBackend",
               "inputs": {"model": ["1", 0], "attention": "comfy kitchen attention"}}
    p["12"]["inputs"]["model"] = ["50", 0]
    gi = p["42"]["inputs"]
    gi["prompt"] = PROMPT
    gi["duration_sec"] = round(FRAMES / 24, 3)
    ins = p["5"]["inputs"]
    ins["seed"] = SEED
    ins["total_frames"] = FRAMES
    tl = json.loads(ins["timeline_data"])
    tl["output"] = {"mode": "fixed", "width": WIDTH, "height": HEIGHT, "longEdge": HEIGHT}
    tl["width"], tl["height"] = WIDTH, HEIGHT
    tl["totalFrames"] = FRAMES
    ins["timeline_data"] = json.dumps(tl, ensure_ascii=False)
    p["45"]["inputs"]["video"] = INPUT_MP4
    p["45"]["inputs"]["frame_load_cap"] = FRAMES
    p["40"]["inputs"]["image"] = PICTURE1
    p["41"]["inputs"]["image"] = PICTURE2
    p["7"]["inputs"]["filename_prefix"] = "video/gen"

    req = urllib.request.Request(safe_url("/prompt"), data=json.dumps(wf).encode(),
                                 headers={"Content-Type": "application/json"})
    pid = json.loads(urllib.request.urlopen(req, timeout=60).read())["prompt_id"]
    print("submitted", pid)
    st = "pending"
    while st in ("pending", "running"):
        time.sleep(20)
        h = json.loads(urllib.request.urlopen(safe_url("/history/" + pid), timeout=30).read())
        hh = list(h.values())[0] if h else {}
        st = hh.get("status", {}).get("status_str", "pending")
        if st == "error":
            for t, m in hh.get("status", {}).get("messages", []):
                if t == "execution_error":
                    print("ERR:", m.get("exception_message", ""))
            raise SystemExit(1)
    print("done:", st)


if __name__ == "__main__":
    main()
