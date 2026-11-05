"""Character-scoped skill-unlock/purchase/learning/preset receipts.

The coordinator never promotes a click/timeout to a successful game receipt.
All game actions are performed by the existing adapter's input-owning worker.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from functools import lru_cache
import hashlib,json,logging,os,time,tempfile
LOG=logging.getLogger('project_gui.DKB')
KST=timezone(timedelta(hours=9))
STORY='도술 구매의 자격 증명'
GATES=(44500,54500,63000,77000,87000)
FINAL=87000

class Pending(RuntimeError):pass

def stamp():return datetime.now(KST).isoformat()
def read(path,default):
    try:return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except FileNotFoundError:return default

def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,temporary=tempfile.mkstemp(prefix='.'+path.name+'-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as out:
            json.dump(data,out,ensure_ascii=False,indent=2)
            out.flush();os.fsync(out.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)

class Ledger:
    def __init__(self,root,character,*,scope=None):
        if not isinstance(character,str) or not character:raise Pending('현재 캐릭터 확인 필요')
        self.path=Path(root)/'settings/owner-skill-goal.json'
        self.data=read(self.path,{'version':1,'characters':{}})
        self.character=character
        self.receipt_key=(character if scope is None else 'scoped-v1:'+hashlib.sha256((scope+'|'+character).encode('utf-8')).hexdigest())
        # Unscoped historic receipts remain intact but cannot authorize a
        # different configured server's purchase or completion skip.
        self.item=self.data.setdefault('characters',{}).setdefault(self.receipt_key,{
            'stage':'story','story_step':0,'status':'pending','purchases':{},'presets':{},'events':[]})
    def save(self):atomic(self.path,self.data)
    def event(self,kind,**fields):
        self.item['events']=(self.item.get('events',[])+[dict(at=stamp(),kind=kind,**fields)])[-200:]
        self.save()
    def hold(self,reason,**fields):
        changed=self.item.get('reason')!=reason or self.item.get('status')!='held'
        self.item.update(status='held',reason=reason,**fields);self.save()
        if changed:LOG.info('도술 육성 보류 · %s',reason)
    def story_receipt(self,step,receipt):
        if step not in range(1,6) or receipt.get('title')!=STORY+str(step) or receipt.get('verified') is not True:
            raise ValueError('도술 서사 완료 증거 불일치')
        if step<self.item['story_step']:return
        self.item.update(story_step=step,status='pending');self.item.pop('reason',None)
        if step==5:self.item['stage']='purchase'
        self.event('story_completed',step=step,receipt=receipt)
    def begin_purchase(self,key,quote,*,tutorial=False):
        tutorial_ok=(tutorial and self.item.get('tutorial_required')=='쇠뇌 사격' and quote.get('item')=='쇠뇌 사격' and self.item['story_step']==1)
        if self.item['story_step']!=5 and not tutorial_ok:raise Pending('도술 해금 서사 최종 완료 확인 전')
        if quote.get('currency')!='엽전' or type(quote.get('price')) is not int or not 1<=quote['price']<=10000 or quote.get('bundles')!=1 or quote.get('fragments')!=100:
            raise Pending('무료 획득 엽전 1묶음/100조각/1만 이하 조건 불일치')
        old=self.item['purchases'].get(key)
        if old and old['status'] in ('intent','confirmed'):return False
        self.item['purchases'][key]=dict(status='intent',at=stamp(),quote=quote)
        self.event('purchase_intent',key=key,quote=quote);return True
    def purchase_receipt(self,key,receipt):
        old=self.item['purchases'].get(key)
        if not old or old['status']!='intent' or receipt.get('item')!=old['quote'].get('item') or receipt.get('verified') is not True:
            raise Pending('구매 완료 증거 불일치')
        old.update(status='confirmed',receipt=receipt,at=stamp());self.event('purchase_confirmed',key=key)
    def preset_receipt(self,mode,slots,order,missing=()):
        if mode!='aoe' or len(slots)!=8 or len(set(x for x in slots if x is not None))!=sum(x is not None for x in slots):raise ValueError('광역 프리셋 슬롯 중복/개수 오류')
        self.item['presets'][mode]={'at':stamp(),'slots':slots,'order':order,'missing_slots':list(missing),'verified':True,'complete':not missing}
        self.event('preset_verified',mode=mode,missing_slots=list(missing))

def runtime_ledger(adapter,character):
    from owner_hunt_rules_candidate import configured_identity
    return Ledger(adapter.project.root,character,scope=configured_identity(adapter.project.root))

@lru_cache(maxsize=1)
def catalog():
    data=read(Path(__file__).with_name('skill_catalog.json'),{})
    if 'aoe' not in data.get('presets',{}):raise Pending('광역 도술 목록 확인 필요')
    for mode,p in (('aoe',data['presets']['aoe']),):
        ids=[s['id'] for s in p['slots']]
        if len(ids)!=8 or len(set(ids))!=8 or set(ids)!={s['id'] for s in p['order']}:raise Pending('추천 슬롯/사용 순서 불일치')
    return data

def requested_plan(mode,owned,unlocked):
    p=catalog()['presets'][mode]
    missing=[s['name'] for i,s in enumerate(p['slots']) if i in unlocked and s['id'] not in owned]
    if missing:raise Pending('미학습 도술: '+', '.join(missing))
    if not set(range(5)).issubset(unlocked):raise Pending('기본 도술 다섯 칸 개방 확인 필요')
    return [s['id'] if i in unlocked else None for i,s in enumerate(p['slots'])], [s['id'] for s in p['order'] if s['id'] in {s['id'] for i,s in enumerate(p['slots']) if i in unlocked}]

def eligible(progress,item):
    if progress.character is None or type(progress.level) is not int or progress.level<50:return False
    if item.get('stage')=='done' and aoe_matches_request(item) and item.get('learning_ids')==sorted(desired_learning_ids()):return False
    required=item.get('required_power')
    # Unknown power authorizes another read, never progression/purchase.
    if required and progress.power is not None and progress.power<required:return False
    return True

def aoe_matches_request(item):
    from owner_aoe_preset_candidate import SLOTS,ORDER
    receipt=item.get('presets',{}).get('aoe',{})
    return (receipt.get('verified') is True and receipt.get('complete') is True
            and receipt.get('slots')==list(SLOTS) and receipt.get('order')==list(ORDER))

PURCHASE_STYLES=('파멸','강타','절명','저격')  # the user's rule. Ultimates are not bought: the deck's slots switch them on.

def desired_learning_ids():
    data=catalog()
    approved={entry['id'] for entry in data['all_skill_names'].values()
              if entry.get('style') in PURCHASE_STYLES and entry.get('ultimate') is not True}
    return approved

def same_skill_context(adapter,context,character,configured):
    """Previously observed character + configured account scope fence.

    This does not claim the game avatar was OCR-read at every click.
    """
    from owner_progression import state
    from owner_hunt_rules_candidate import configured_identity
    try:
        current=state(adapter);age=time.monotonic()-current.observed
        return (current.character==character and 0<=age<=300
                and configured_identity(adapter.project.root)==configured
                and getattr(adapter,'_owner_skill_context',None) is context)
    except (OSError,ValueError,TypeError):return False

def complete_requested_aoe(ui,ledger,character,checkpoint):
    """Reuse the existing owned scan, avoiding purchase of learned skills."""
    from owner_aoe_preset_candidate import SLOTS,ORDER
    if ledger.character!=character:raise Pending('현재 캐릭터·도술 기록 불일치')
    if ledger.item.get('story_step')!=5:raise Pending('도술 서사 최종 완료 확인 전')
    if ledger.item.get('stage')=='done':
        if aoe_matches_request(ledger.item) and ledger.item.get('learning_ids')==sorted(desired_learning_ids()):return True
        ledger.item['stage']='purchase';ledger.save()
    if ledger.item.get('stage')=='presets' and ledger.item.get('learning_ids')!=sorted(desired_learning_ids()):
        ledger.item['stage']='purchase';ledger.save()
    required=desired_learning_ids()
    if ledger.item['stage'] in ('purchase','learning_pending'):
        owned=ui.scan_owned();checkpoint()
        if not isinstance(owned,set):raise Pending('현재 보유 도술 확인 필요')
        if not required.issubset(owned):
            reason=None
            try:
                result=ui.purchase_required_and_learn(ledger)
                if result is not True and (not isinstance(result,dict) or result.get('status') not in ('partial','completed')):
                    raise Pending('요청 도술 구매·학습 확인 필요')
            except Pending as exc:
                # An unavailable purchase/individual-learning proof is not a
                # reason to deny an already-owned AoE preset. First exit only
                # recognized transient UI, then perform a fresh owned scan.
                # Never reinterpret the uncertain transaction as successful.
                reason=str(exc)
                checkpoint();ui.close_known();checkpoint()
            checkpoint();owned=ui.scan_owned();checkpoint()
            if not isinstance(owned,set):raise Pending('요청 도술 학습 후 목록 확인 필요')
            if reason:
                ledger.item['requested_learning']={'styles':['파멸','강타'],'status':'partial','reason':reason}
        missing=required-owned
        ledger.item.update(owned_skills=sorted(owned),learning_missing=sorted(missing))
        if not missing:
            ledger.item['learning_ids']=sorted(required)
            ledger.item['requested_learning']={'styles':['파멸','강타'],'status':'completed','owned_skills':sorted(owned),'verified':True}
        else:
            # A preset receipt does not complete the separate all-style goal.
            # In particular, never reinterpret a held gold purchase as learned.
            ledger.item.pop('learning_ids',None)
        ledger.save()
        # 대폭발은 같은 계열 장착 후 사용 순서 화면에서 검증한다.
        # 슬롯 배치 전 궁극기를 보유 목록에서 요구하면 순환 대기가 난다.
        if not set(SLOTS).issubset(owned):raise Pending('광역 구성에 필요한 도술 학습 미완료')
        ledger.item['stage']='presets';ledger.save()
    if ledger.item['stage']=='presets':
        import owner_skill_ui
        from owner_aoe_skill_bridge_candidate import attempt_live_candidate
        if not aoe_matches_request(ledger.item):
            checkpoint()
            if attempt_live_candidate(owner_skill_ui,ui,ledger,character=character,checkpoint=checkpoint) is not True:
                raise Pending('광역 프리셋 저장 확인 필요')
        if not aoe_matches_request(ledger.item):raise Pending('광역 프리셋 완료 기록 불일치')
        if ledger.item.get('learning_ids')!=sorted(required):
            ledger.item.update(stage='learning_pending',status='partial',reason='광역 구성 완료 · 나머지 도술 학습 대기')
            ledger.event('requested_aoe_completed_learning_pending')
            return True
        ledger.item.update(stage='done',status='completed');ledger.item.pop('reason',None)
        ledger.event('requested_aoe_completed')
        return True
    return False

def execute(adapter,context,inputs,*,force=False):
    """At a safe work opportunity; no second input loop or background clicks."""
    if getattr(adapter,'_owner_stationary_mode',False):return False
    if getattr(adapter,'_owner_skill_busy',False):return False
    if getattr(adapter,'_owner_catalog_enabled',False) and not getattr(adapter,'_owner_quest_boundary',False):return False
    if not force and time.monotonic()-getattr(adapter,'_owner_skill_checked',-1e30)<300:return False
    from owner_schedule_priority import hold_reason,LOCAL
    if hold_reason(adapter) or getattr(LOCAL,'feature',None) or context.input_depth or getattr(inputs,'held',()):return False
    # This wrapper runs before timetable.idle_once. Respect the same owner
    # here too; its downstream guard cannot protect an earlier skill action.
    from owner_timetable import LOCAL as timetable_owner
    if getattr(timetable_owner,'job',None) or getattr(timetable_owner,'native_job',None):return False
    adapter._owner_skill_checked=time.monotonic()
    from owner_progression import state
    progress=state(adapter)
    if progress.character is None or time.monotonic()-progress.observed>300 or getattr(adapter,'_owner_skill_context',None) is not context:
        from owner_quest_preflight import read_power
        started=time.monotonic()
        verified=read_power(adapter,context,inputs)
        if not verified or progress.observed<started:return False
        adapter._owner_skill_context=context
    if progress.character is None or type(progress.level) is not int or progress.level<50:return False
    from owner_hunt_rules_candidate import configured_identity
    configured=configured_identity(adapter.project.root)
    ledger=runtime_ledger(adapter,progress.character)
    if getattr(adapter,'_owner_catalog_enabled',False) and ledger.item.get('stage')=='story' and not force:
        # The quest controller owns progression. Wait for its actual final
        # completion receipt; do not open a search overlay before every pick.
        return False
    character=progress.character
    def identity_guard():return same_skill_context(adapter,context,character,configured)
    def guarded_checkpoint():
        context.checkpoint()
        if identity_guard() is not True:raise Pending('현재 캐릭터·설정 재확인 필요')
    if not eligible(progress,ledger.item):return False
    from owner_skill_ui import SkillUI
    previous=getattr(LOCAL,'feature',None);LOCAL.feature='도술 해금·구매·학습·프리셋'
    adapter._owner_skill_busy=True;ui=None
    try:
        context.checkpoint();adapter.exit_sleep_mode(context,inputs)
        ui=SkillUI(adapter,context,inputs);ui._owner_identity_guard=identity_guard
        guarded_checkpoint()
        if not ui.normal():return False
        ledger.item['resume_mode']=adapter.mode;ledger.save()
        if ledger.item['stage']=='story':
            if getattr(adapter,'_owner_catalog_enabled',False):
                # The mission catalog owns actual quest execution. This
                # reconciliation only reads the final quest's clear marks.
                if not ui.confirm_final_story(ledger):return False
            else:ui.story(ledger,progress)
            if ledger.item['stage']=='story':return True
        if ledger.item['stage'] in ('purchase','presets','done','learning_pending'):
            return complete_requested_aoe(ui,ledger,character,guarded_checkpoint)
        return True
    except Pending as exc:
        ledger.hold(str(exc));return True
    finally:
        try:
            if ui:ui.close_known()
        finally:
            LOCAL.feature=previous;adapter._owner_skill_busy=False

def install(gui):
    if getattr(gui,'_owner_skill_goal',False):return
    from functools import wraps
    import owner_timetable,owner_task_flow
    ordinary_idle=owner_timetable.idle_once
    @wraps(ordinary_idle)
    def idle(adapter,context,inputs):
        if execute(adapter,context,inputs):
            context.checkpoint()
            if adapter.mode=='auto_mode' and adapter.run_favorite_hunt(context,inputs) is not True:raise Pending('도술 처리 후 원래 사냥터 복귀 미확인')
            return True
        return ordinary_idle(adapter,context,inputs)
    owner_timetable.idle_once=idle
    ordinary_dispatch=owner_task_flow.dispatch
    @wraps(ordinary_dispatch)
    def dispatch(adapter,context,ordinary):
        item=owner_task_flow.pending(adapter,context)
        if item and execute(adapter,context,item['inputs']):
            resume=getattr(adapter,'_owner_skill_return_mode',None)
            adapter._owner_skill_return_mode=None
            if resume in ('main_quest','sub_quest'):
                from owner_work_resume import ResumeWork
                raise ResumeWork(resume,allow_growth=False)
            return True
        return ordinary_dispatch(adapter,context,ordinary)
    owner_task_flow.dispatch=dispatch
    gui._owner_skill_goal=True
    LOG.info('도술 육성 준비 · 최종 서사 후 학습 · 광역 프리셋 1만 사용')
