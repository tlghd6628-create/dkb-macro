from pathlib import Path
import sys,os,json
T=Path(__file__).resolve().parent; R=Path('C:/Users/홍이/Downloads/도깨비의 세계');O=R/'owner';A=R/'vendor/DKB_Auto';B=R/'vendor/BIOL_Project_Base/1.1.0';RT=R/'vendor/BIOL_Runtime/1.1.0'
sys.path[:0]=[str(T),str(O),str(A),str(B/'tools'),str(B),str(RT/'code')];sys.dont_write_bytecode=True
os.environ.update(MDT_SHARED_APP_ROOT=str(A),MDT_RUNTIME_PRODUCT='DKB',MDT_SHARED_RUNTIME_HOME=str(RT.parent),MDT_SHARED_BIOL_DLL=str(RT/'native/BIOL_OCR.dll'))
