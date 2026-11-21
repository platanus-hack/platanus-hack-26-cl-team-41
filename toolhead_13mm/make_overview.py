"""Compose the inspected CAD renders into a labeled review image."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent/'renders'
font=Path('C:/Windows/Fonts/segoeui.ttf');bold=Path('C:/Windows/Fonts/segoeuib.ttf')
canvas=Image.new('RGB',(1600,900),'#eef1f4');d=ImageDraw.Draw(canvas)
def text(x,y,s,size=24,strong=False):d.text((x,y),s,font=ImageFont.truetype(str(bold if strong else font),size),fill='#172735')
text(35,20,'13 mm angled toolhead',34,True)
text(35,68,'45° collar  •  40 mm usable cool handle  •  M3 fasteners',24)
for x,name in ((0,'assembly.png'),(800,'latch_open.png')):
    im=Image.open(ROOT/name).convert('RGB').resize((800,727),Image.Resampling.LANCZOS);canvas.paste(im,(x,115))
d.rectangle((0,800,1600,900),fill='#eef1f4')
text(30,810,'Assembly — 30 mm split collar',24,True)
text(820,810,'Cutaway — jaws opened 5.5° behind lip',24,True)
text(30,852,'Cold-fit CAD prototype. Load capacity, print fit and heated operation remain unverified.',22)
canvas.save(ROOT/'overview.png')
