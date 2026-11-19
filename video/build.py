"""Builds the demo video from real screenshots of a live run, with captions."""
import subprocess, pathlib, sys
TR = "/Users/claw/.claude/projects/-Users-claw-Documents/ccd79936-e517-4a4b-a1fd-fda6eaf448cc/tool-results/"
P = "mcp-claude-in-chrome-blob-1795048813165-"
F = lambda s, pre=P: TR + pre + s + ".jpg"
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT2 = "/System/Library/Fonts/Supplemental/Arial.ttf"
W, H, BAR = 1568, 662, 150
shots = [
    (None, 6, "Diya SOC|Red vs Blue security agents that harden an app together, inside a BAND room. Brains on Lyzr."),
    (F("nf1kbi"), 7, "The range: a deliberately vulnerable Diwali sweets shop with 4 real bugs. 0 of 4 closed."),
    (F("elqoon"), 6, "A human asks the Red agent to attack, from a shared BAND room with Red and Blue in it."),
    (F("cvyiur"), 5, "Red posts its plan to the room as a live Thought event."),
    (F("zn3fyl"), 7, "Real exploits land: SQL injection, XSS, IDOR and a secrets leak. 4 red hits on the range."),
    (F("8itufi"), 9, "Red files one BAND task per finding and @mentions Blue with a machine-readable handoff."),
    (F("3si435"), 5, "Blue picks it up, moves the tasks to in progress and triages."),
    (F("pdjml7"), 9, "Blue ships patches plus a detection rule for each bug, then @mentions Red: RETEST."),
    (F("drr3ux"), 8, "Red re-attacks. Every exploit is now BLOCKED and the diyas light up: 4 of 4."),
    (TR + "mcp-claude-in-chrome-blob-1795048821808-dxqft5.jpg", 7, "Red reports back to the human: verified closed. Happy Diwali, the lights stay on."),
    (TR + "mcp-claude-in-chrome-blob-1795048813166-i6az2s.jpg", 8, "The BAND task board: every finding Done, 2 of 2 agents signed off. Fully auditable."),
    (None, 7, "Two agents. One BAND room. Every step visible.|github.com/techadnank9/diya-soc"),
]
out = pathlib.Path("seg"); out.mkdir(exist_ok=True)
from PIL import Image, ImageDraw, ImageFont
fb = lambda n: ImageFont.truetype(FONT, n); fr = lambda n: ImageFont.truetype(FONT2, n)
BG, CREAM, GOLD = (15, 11, 8), (244, 233, 220), (255, 181, 71)
def center(d, y, text, font, fill):
    w = d.textlength(text, font=font); d.text(((W - w) / 2, y), text, font=font, fill=fill)
parts = []
for i, (img, dur, cap) in enumerate(shots):
    canvas = Image.new("RGB", (W, H + BAR), BG); d = ImageDraw.Draw(canvas)
    if img is None:
        title, sub = cap.split("|")
        center(d, (H + BAR) / 2 - 120, title, fb(92), GOLD)
        center(d, (H + BAR) / 2 + 10, sub, fr(34), CREAM)
    else:
        canvas.paste(Image.open(img).convert("RGB").resize((W, H)), (0, 0))
        d.rectangle([0, H, W, H + 4], fill=GOLD)
        center(d, H + (BAR - 40) / 2, cap, fb(34), CREAM)
    png = out / f"{i:02d}.png"; canvas.save(png)
    seg = out / f"{i:02d}.mp4"
    vf = (f"zoompan=z='min(zoom+0.0003,1.03)':d={dur*30}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H+BAR}:fps=30,"
          f"fade=in:0:10,fade=out:{dur*30-8}:8")
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(png),"-vf",vf,"-frames:v",str(dur*30),
                    "-c:v","libx264","-pix_fmt","yuv420p","-r","30",str(seg)], check=True)
    parts.append(seg)
(out / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in parts))
subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0","-i",str(out/"list.txt"),"-c","copy","diya-soc-demo.mp4"], check=True)
print("total", sum(d for _, d, _ in shots), "s")
