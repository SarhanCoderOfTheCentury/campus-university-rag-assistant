"""Compose actual browser capture frames into a 1080p captioned product film.

Input is a capture manifest with real screenshots and durations. No product UI,
answers, retrieval states or latency figures are synthesized by this renderer.
"""
import argparse,json,math,subprocess,wave
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter

ROOT=Path(__file__).resolve().parents[1]
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def font(size,bold=False):return ImageFont.truetype(BOLD if bold else FONT,size)

def lines(draw,text,xy,width,size,color,bold=False,spacing=1.32):
    x,y=xy;f=font(size,bold);line=''
    for word in text.split():
        candidate=(line+' '+word).strip()
        if draw.textlength(candidate,font=f)>width and line:
            draw.text((x,y),line,font=f,fill=color);y+=int(size*spacing);line=word
        else:line=candidate
    if line:draw.text((x,y),line,font=f,fill=color);y+=int(size*spacing)
    return y

def frame(scene,progress):
    canvas=Image.new('RGB',(1920,1080),'#f4f5f1');d=ImageDraw.Draw(canvas)
    d.rounded_rectangle((56,46,102,92),radius=14,fill='#202b23')
    d.line([(68,69),(80,62),(92,69),(80,76),(68,69)],fill='#e7eddf',width=2)
    d.line([(72,73),(72,79),(80,83),(88,79),(88,73)],fill='#e7eddf',width=2)
    d.text((119,48),'Campus',font=font(30,True),fill='#202b23')
    d.text((119,86),'UNIVERSITY ASSISTANT',font=font(12),fill='#68746a',spacing=2)
    d.text((62,226),scene['eyebrow'].upper(),font=font(14,True),fill='#76876d')
    bottom=lines(d,scene['title'],(58,266),405,48,'#202b23',True,1.19)
    lines(d,scene['description'],(62,bottom+30),385,22,'#617067',spacing=1.5)
    d.line((62,766,414,766),fill='#cbd2c6',width=1)
    d.text((62,790),'DOCUMENT-GROUNDED',font=font(13,True),fill='#68746a')
    d.text((62,820),'Real questions. Real source evidence.',font=font(17),fill='#617067')
    image=Image.open(scene['file']).convert('RGB');image.thumbnail((1362,936),Image.Resampling.LANCZOS)
    x=506+(1362-image.width)//2;y=103+(936-image.height)//2
    shadow=Image.new('RGBA',canvas.size);sd=ImageDraw.Draw(shadow)
    sd.rounded_rectangle((x-2,y+8,x+image.width+2,y+image.height+8),radius=18,fill=(30,40,25,25))
    canvas=Image.alpha_composite(canvas.convert('RGBA'),shadow.filter(ImageFilter.GaussianBlur(15))).convert('RGB')
    mask=Image.new('L',image.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,image.width,image.height),radius=14,fill=255)
    canvas.paste(image,(x,y),mask);d=ImageDraw.Draw(canvas)
    d.rounded_rectangle((x-1,y-1,x+image.width,y+image.height),radius=15,outline='#d6dbd1',width=1)
    d.text((511,60),'LIVE PRODUCT WALKTHROUGH',font=font(13,True),fill='#617067')
    d.text((62,1004),'Vercel frontend  /  AWS agent',font=font(14),fill='#617067')
    d.text((62,1030),'Actual UI capture; selected pauses trimmed.',font=font(12),fill='#859080')
    d.rectangle((0,1074,1920,1079),fill='#e2e6dc');d.rectangle((0,1074,int(progress*1920),1079),fill='#879c72')
    return canvas

def soundtrack(path,duration):
    rate=48000;t=np.arange(int(duration*rate))/rate;audio=np.zeros_like(t)
    # Quiet, original four-chord ambient bed. No third-party music assets.
    chords=[[130.813,164.814,195.998],[110,130.813,164.814],[87.307,110,130.813],[97.999,123.471,146.832]]
    for start in np.arange(0,duration,6):
        local=t-start;mask=(local>=0)&(local<8);u=local[mask]
        env=np.minimum(u/1.7,1)*np.minimum((8-u)/2.5,1)
        for frequency in chords[int(start/6)%4]:
            audio[mask]+=.023*env*(np.sin(2*np.pi*frequency*u)+.15*np.sin(2*np.pi*frequency*2*u))
    audio*=np.minimum(t/2,1)*np.minimum((duration-t)/3,1)
    pcm=(np.stack([audio,audio*.95],axis=1)*32767).astype('<i2')
    with wave.open(str(path),'wb') as w:w.setparams((2,2,rate,len(t),'NONE','not compressed'));w.writeframes(pcm.tobytes())

def main():
    p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);p.add_argument('--output',type=Path,default=ROOT/'demo.mp4');a=p.parse_args()
    scenes=json.loads(a.manifest.read_text());work=ROOT/'.deploy/demo-render';work.mkdir(parents=True,exist_ok=True)
    duration=sum(s['duration'] for s in scenes);elapsed=0;concat=[]
    for i,scene in enumerate(scenes):
        image=frame(scene,(elapsed+scene['duration']/2)/duration);path=work/f'frame-{i:04d}.png';image.save(path)
        concat.extend(["file '"+str(path)+"'",'duration '+str(scene['duration'])]);elapsed+=scene['duration']
    concat.append("file '"+str(path)+"'");(work/'frames.txt').write_text('\n'.join(concat)+'\n')
    soundtrack(work/'score.wav',duration)
    command=['ffmpeg','-hide_banner','-loglevel','warning','-y','-f','concat','-safe','0','-i',str(work/'frames.txt'),'-i',str(work/'score.wav'),'-vf',f'fps=30,fade=t=in:st=0:d=0.6,fade=t=out:st={duration-.7}:d=0.7','-t',str(duration),'-c:v','libx264','-preset','medium','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',str(a.output)]
    subprocess.run(command,check=True);print(json.dumps({'file':str(a.output),'seconds':duration,'bytes':a.output.stat().st_size}))

if __name__=='__main__':main()
