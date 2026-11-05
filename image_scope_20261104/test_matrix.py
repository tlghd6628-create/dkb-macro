"""Press each feature's TEST button in turn and keep its log, so a success count comes from real runs.
Usage: test_matrix.py OUTFILE LIMIT NAME...   (no names: the list below, in order). The game must be on the field."""
from pathlib import Path
import subprocess,sys,time,re,os
ROOT=Path(os.environ.get('DKB_ROOT') or r'C:\Users\홍이\Downloads\도깨비의 세계')
PY=str(ROOT/'vendor/BIOL_Runtime/1.1.0/python/python.exe')
D=Path(__file__).parent
LOG=ROOT/'vendor/DKB_Auto/logs'/(time.strftime('%Y-%m-%d')+'.log')
# name: (settings nav y, button x, button y)
TESTS={'장비':(341,579,143),'도술':(371,350,141),'가호':(401,350,142),'가호보상':(401,466,530),'기운':(431,350,142),'화첩':(461,350,142),
 '영기':(581,467,163),'일일임무':(551,466,163),'주간임무':(551,466,194),'보물찾기':(551,466,225),'비경일일':(551,466,390),'상점':(221,408,115),
 '승천':(551,473,290),'월드보스':(551,854,163),'낙화':(551,854,264),'전래':(551,854,328),'레이드':(551,854,390)}
SKIP=re.compile('상태판정|화면 자료 저장|정보창 열림|퀘스트 조건|육성 상태|Paddle|세부설정|OCR')
def run(*a):return subprocess.run([PY,*a],cwd=D,capture_output=True,text=True,encoding='utf-8',errors='replace').stdout
out=Path(sys.argv[1]);limit=sys.argv[2];names=sys.argv[3:] or list(TESTS)
with out.open('a',encoding='utf-8') as sink:
    for name in names:
        tab,x,y=TESTS[name]
        run('f3_stop.py');time.sleep(7)
        if '세부설정' not in run('gui_tool.py','list'):
            run('gui_tool.py','click','DKB ·','445','384','m0','2.5')
        size=LOG.stat().st_size;started=time.time()
        result=run('run_test.py','matrix_'+name,str(tab),str(x),str(y),limit)
        text=LOG.read_bytes()[size:].decode('utf-8','replace')
        lines=[l[11:190] for l in text.splitlines() if re.match(r'\d{4}-',l) and not SKIP.search(l)]
        sink.write('=== %s %.0fs\n%s\n'%(name,time.time()-started,'\n'.join(lines[-14:])));sink.flush()
        run('game_shot.py','matrix_'+name)
run('f3_stop.py')
