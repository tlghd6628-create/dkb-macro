from pathlib import Path
import sys,os
r=Path('C:/Users/홍이/Downloads/FC_프로그램/도깨비의세계/테스트/DKB_로컬개발용_v0.9.3.1_20261031');a=r/'vendor/DKB_Auto';b=r/'vendor/BIOL_Project_Base/1.1.0';rt=r/'vendor/BIOL_Runtime/1.1.0'
sys.dont_write_bytecode=True;sys.path[:0]=[str(Path(__file__).resolve().parent),str(r/'owner'),str(a),str(b/'tools'),str(b),str(rt/'code')];os.environ.update(MDT_SHARED_APP_ROOT=str(a),MDT_RUNTIME_PRODUCT='DKB',MDT_SHARED_RUNTIME_HOME=str(rt.parent),MDT_SHARED_BIOL_DLL=str(rt/'native/BIOL_OCR.dll'))
from PIL import Image
import numpy as np
from types import SimpleNamespace as NS
from owner_mission_ui import MissionUI
f=np.asarray(Image.open(a/'logs/scene-corpus/20261101/20261101T162524-52156c47/screen.png'))
ui=object.__new__(MissionUI);ui.adapter=NS(mode='sub_quest',project=NS(root=a,code='DKB'));ui.frame=lambda:f;ui.context=NS(wait=lambda x:None)
assert ui.execution_dialogue_pair()
print('saved actual failure frame: paired native dialogue recognition PASS; no input')
