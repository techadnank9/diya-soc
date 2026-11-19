"""Narrated demo: real screenshots of a live run + macOS voiceover + burned-in and soft subtitles."""
import subprocess, pathlib, textwrap
from PIL import Image, ImageDraw, ImageFont
TR = "/Users/claw/.claude/projects/-Users-claw-Documents/ccd79936-e517-4a4b-a1fd-fda6eaf448cc/tool-results/mcp-claude-in-chrome-blob-"
A, B, C = TR + "1795058987631-", TR + "1795059016590-", TR + "1795059016591-"
FONT, FONT2 = "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"
W, H, BAR = 1568, 662, 170
shots = [
    (None, "Diya SOC|Red versus Blue security agents, collaborating in a BAND room, with Lyzr brains.",
     "Meet Diya SOC. Two security agents, Red and Blue, that harden an app together inside a BAND room, with their reasoning running on Lyzr."),
    (TR+"1795059074738-nsa14f.jpg", None, "Both agents are registered in BAND as remote agents, Red and Blue, online and ready."),
    (TR+"1795059093895-i8hlcb.jpg", None, "Their reasoning runs on Lyzr Agent Studio: a Red Team Analyst and a Blue Team Engineer."),
    (A+"fmllb3.jpg", None, "This is our test range: a Diwali sweets shop with four real vulnerabilities. Zero of four are closed."),
    (A+"3oike5.jpg", None, "From a shared BAND room, a human simply asks the Red agent to attack the shop."),
    (A+"8z844s.jpg", None, "Red posts its plan to the room as a live thought event, so everyone can follow along."),
    (A+"6yztpi.jpg", None, "Real exploits land: SQL injection, cross site scripting, an IDOR, and a secrets leak."),
    (A+"8sw375.jpg", None, "Red's Lyzr brain writes a severity report. Red files one BAND task per finding and mentions Blue."),
    (B+"mm9iwn.jpg", None, "Blue's Lyzr brain returns the root cause, a code fix, and a detection rule. Blue deploys, then asks Red to retest."),
    (C+"unii1t.jpg", None, "Red attacks again. Every exploit is now blocked, and the diyas light up. Four of four."),
    (C+"tewijk.jpg", None, "Red reports the verdict back to the human. Happy Diwali, the lights stay on."),
    (C+"skml9w.jpg", None, "On the BAND task board, all four findings are done, signed off by both agents."),
    (None, "Two agents. One BAND room.|github.com/techadnank9/diya-soc",
     "Two agents, one BAND room, every step visible and auditable. That's Diya SOC."),
]
out = pathlib.Path("seg_v"); out.mkdir(exist_ok=True)
fb = lambda n: ImageFont.truetype(FONT, n); fr = lambda n: ImageFont.truetype(FONT2, n)
BG, CREAM, GOLD = (15, 11, 8), (244, 233, 220), (255, 181, 71)
def center(d, y, text, font, fill):
    d.text(((W - d.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)
def ts(t):
    ms = int(round(t * 1000)); return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"
segs, srt, t = [], [], 0.0
for i, (img, card, line) in enumerate(shots):
    aiff = out / f"{i:02d}.aiff"
    subprocess.run(["say", "-v", "Samantha", "-r", "185", "-o", str(aiff), line], check=True)
    alen = float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(aiff)]))
    dur = round(alen + 0.9, 2)
    canvas = Image.new("RGB", (W, H + BAR), BG); d = ImageDraw.Draw(canvas)
    if img is None:
        title, sub = card.split("|")
        center(d, (H + BAR) / 2 - 150, title, fb(92), GOLD)
        center(d, (H + BAR) / 2 - 20, sub, fr(34), CREAM)
    else:
        canvas.paste(Image.open(img).convert("RGB").resize((W, H)), (0, 0))
    d.rectangle([0, H, W, H + 4], fill=GOLD)
    lines = textwrap.wrap(line, 78)
    y0 = H + (BAR - 46 * len(lines)) / 2
    for k, l in enumerate(lines):
        center(d, y0 + 46 * k, l, fb(34), CREAM)
    png = out / f"{i:02d}.png"; canvas.save(png)
    seg = out / f"{i:02d}.mp4"; n = int(dur * 30)
    vf = (f"zoompan=z='min(zoom+0.0003,1.03)':d={n}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H+BAR}:fps=30,"
          f"fade=in:0:8,fade=out:{n-8}:8")
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(png),"-i",str(aiff),"-vf",vf,"-af",f"apad,atrim=0:{dur}",
                    "-frames:v",str(n),"-c:v","libx264","-pix_fmt","yuv420p","-r","30","-c:a","aac","-ar","44100","-ac","2",
                    "-shortest",str(seg)], check=True)
    srt.append(f"{i+1}\n{ts(t+0.2)} --> {ts(t+alen+0.2)}\n" + "\n".join(lines) + "\n")
    segs.append(seg); t += dur
(out / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in segs))
pathlib.Path("diya-soc-demo.srt").write_text("\n".join(srt))
subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0","-i",str(out/"list.txt"),"-i","diya-soc-demo.srt",
                "-map","0:v","-map","0:a","-map","1:0","-c:v","copy","-c:a","aac","-c:s","mov_text",
                "-metadata:s:s:0","language=eng","-movflags","+faststart","diya-soc-demo.mp4"], check=True)
print(f"total {t:.1f}s")
