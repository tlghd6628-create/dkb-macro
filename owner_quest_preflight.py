"""Fresh character/power preflight on proved normal screens only."""
import re,threading,time,logging
from owner_progression import state,inventory_parts,observe_inventory,resized,texts
LOG=logging.getLogger('project_gui.DKB')


def read_power(adapter,context,inputs,again=False):
    from project_adapter import market_inventory,guide_rewards,favorite_hunt
    from project_adapter.town_services import TownServices
    from project_adapter.secret_exploration import AUTO_NAMES
    from owner_startup_stage import scene,DUNGEON,EXIT,MENU
    from owner_special_contexts import NAMES
    adapter.exit_sleep_mode(context,inputs)
    names=list(dict.fromkeys([DUNGEON,EXIT,MENU,'체크_사망상태',*AUTO_NAMES,*NAMES,
                            *market_inventory.INVENTORY_USE_NAMES,*guide_rewards.NAMES,*favorite_hunt.NAMES]))
    service=TownServices(adapter,context,inputs,names)
    # Closing a menu leaves a moment of neither, and a miss here put the gear visit off by ten minutes.
    for attempt in range(8):
        first=scene(service.detector,service.capture());context.wait(.15)
        second=scene(service.detector,service.capture())
        if first==second and second!='unknown':break
        context.wait(.4);context.checkpoint()
    if first!=second or second not in ('field','inventory'):
        LOG.info('퀘스트 전투력 확인 보류 · 현재 특수환경/전환 화면=%s/%s',first,second);return False
    started=time.monotonic();previous_observed=state(adapter).observed
    # A field restart can expose the HUD inventory icon while the old native
    # OFF-state template is absent. Reuse the existing I-key opener, which
    # accepts only paired left/right panels instead of the HUD OFF marker.
    from owner_progression import open_inventory_by_key
    LOG.info('퀘스트 조건 확인 · 캐릭터·전투력 조회',extra={'gui_message':'퀘스트 조건 확인 · 캐릭터·전투력 조회'})
    if open_inventory_by_key(service) is False:return False
    # The ordinary inventory wrapper may already have a fresh read. Force is
    # needed only for same-session Stop/Start with a new character/equipment.
    progress=state(adapter)
    success=progress.observed>=started or observe_inventory(service,force=True)
    # A combat effect can spoil the one look that decides to press the key, and
    # the panels then stay open. Press again only on a fresh proof both are up.
    # A dimmed guide can start once the bag opens: it blocks the key and spoils
    # what was just read, so it is answered and the read is done again.
    from owner_startup_stage import guide_visible,guide_handler
    end=time.monotonic()+6;pressed=-9.;guided=False;limit=time.monotonic()+60
    while time.monotonic()<end:
        context.checkpoint();frame=service.capture();parts=inventory_parts(frame)
        if time.monotonic()<limit and guide_visible(adapter,frame,service.capture()):
            if guide_handler(adapter,context,inputs,service).handle_tutorial_if_present() in ('FAILED','DETECTED_BUT_UNSAFE'):
                raise RuntimeError('인벤토리 위 안내 입력을 확인하지 못했습니다.')
            guided=True;end=time.monotonic()+6;context.wait(.6);continue
        if not any(parts):break
        if parts==(True,True) and time.monotonic()-pressed>=1.5:
            service.check();service.key(0x49);pressed=time.monotonic()
        context.wait(.1)
    else:raise RuntimeError('전투력 확인 후 인벤토리가 닫히지 않아 퀘스트 입력을 보류합니다.')
    if guided and not again:
        LOG.info('인벤토리 위 안내 처리 · 캐릭터·전투력 다시 확인')
        context.wait(1);return read_power(adapter,context,inputs,again=True)
    # This receipt belongs to this running worker's context and only a newly
    # paired inventory read. A later safe growth opportunity may reuse it
    # briefly instead of reopening inventory during a zone transition.
    if (progress.character and type(progress.level) is int and
        progress.observed>=started and progress.observed>previous_observed):
        adapter._owner_progression_observation=(context,progress.observed,progress.character)
    return success and progress.power is not None


def parse_quest(pages):
    labels=[];chapter=None
    for text,score in texts(pages):
        clean=re.sub(r'\s+',' ',text).strip()
        if score<.94:continue
        match=re.search(r'(?:제\s*)?(\d{1,2})\s*장\b',clean)
        if match:chapter=int(match[1])
        # Keep only named text, not changing counts/distances/combat power.
        if len(re.findall(r'[가-힣]',clean))>=3 and not re.search(r'\d|수락|자동|포기|전투력|완료',clean):labels.append(clean)
    if not labels and chapter is None:return None
    return {'chapter':chapter,'tracker_text':labels,'source':'two_matching_tracker_reads'}


def read_quest(adapter,context,inputs):
    """Optional metadata only. Missing text cannot unlock/clear a block."""
    from project_adapter.town_services import TownServices
    from tools.ocr_support import get_paddle_engine
    progress=state(adapter)
    old=getattr(adapter,'_owner_quest_text_job',None)
    if old and old.is_alive():return
    service=TownServices(adapter,context,inputs,[])
    frames=[service.capture()];context.wait(.12);context.checkpoint();frames.append(service.capture())
    if any(getattr(f,'shape',None)!=(479,897,3) for f in frames):return
    result=[];done=threading.Event();started=time.monotonic()
    def read():
        try:
            engine=get_paddle_engine(adapter.project.root,language='korean')
            result.extend(parse_quest(engine.predict(resized(f,(732,49,155,194)))) for f in frames)
        except Exception:pass
        finally:done.set()
    worker=threading.Thread(target=read,name='dkb-quest-label',daemon=True);adapter._owner_quest_text_job=worker;worker.start()
    while not done.is_set() and time.monotonic()-started<3:context.wait(.05);context.checkpoint()
    if done.is_set() and time.monotonic()-started<=3 and len(result)==2 and result[0] and result[0]==result[1]:
        progress.set_quest(adapter.mode,result[0])
        LOG.info('퀘스트 기록 문맥 확인 · 모드=%s · 장=%s · 표시=%s',adapter.mode,result[0]['chapter'],result[0]['tracker_text'])
    else:progress.set_quest(adapter.mode,None)
