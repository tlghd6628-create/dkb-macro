"""Non-committing feature checks: inspect contracts, then an optional menu probe.

Native run_* functions are inspected for existence, never called here. Menu
probes must be provided separately; file checks alone never prove game behavior.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import copy,importlib,json,os,tempfile,time,io,inspect,types
from owner_feature_check_status_candidate import status as display_status,assessment,summarize,verification,level_counts

KST=timezone(timedelta(hours=9))
RESULTS=frozenset(('정상','확인 필요','오류','중지'))
STAGES=frozenset(('config','contract','menu','values','action_ready','unsupported','skipped'))


def _contract_stage(item,failures,missing,setting):
    """The exact blocked point after file/contract inspection, not a generic hold."""
    if item.get('disabled_by_user'):return 'unsupported','disabled'
    if failures:return 'contract','contract_error'
    if missing:return 'config','settings_missing'
    if setting=='꺼짐':return 'config','settings_off'
    return 'contract',None


def _observation_stage(observation,verified,decision):
    """A probe reports its own stage when it can; otherwise infer the narrowest one."""
    stage=observation.get('stage');finding=observation.get('finding')
    if stage in STAGES:return stage,finding
    if verified and decision:return 'action_ready',None
    if verified:return 'action_ready','decision_not_probed'
    text=str(observation.get('detail',''))
    if '인식 실패' in text or '두 번 확인 실패' in text:return 'menu','menu_unrecognized'
    if '현재 화면' in text:return 'menu','field_not_proven'
    return 'menu','probe_error'


UNPROBED_REASONS={
    **{key:'admission_prohibited' for key in ('raid','field_boss','tower','treasure','falling','falling_elite','clan_artifact','clan_garden','mangwi')},
    **{key:'config_only' for key in ('hunt','potion','inner_path','daily_restart')},
    **{key:'no_nav_anchor' for key in ('coupon','achievement','training_log','market','disassembly','daily_shop','weekly_shop','offline','season')},
    **{key:'runtime_only' for key in ('shop','box_choice','gear_swap','skill_learn','work_resume','reconnect','user_controls','telegram','auto_update')},
}


def coverage():
    """Honest probe coverage, computed from the catalog and the live path table."""
    from owner_feature_check_catalog_candidate import CHECKS
    ids={item['id'] for item in CHECKS}
    try:
        from owner_feature_check_live_candidate import PATHS,DIRECT
        probed=set(PATHS)|set(DIRECT)|{'main','sub','daily_quest','weekly_quest','folktale','inventory','skill_preset'}
    except Exception:
        probed=set()
    schedule={item['id'] for item in CHECKS if item.get('schedule_only')}
    disabled={item['id'] for item in CHECKS if item.get('disabled_by_user')}
    unprobed=sorted(ids-probed-schedule-disabled)
    from owner_feature_check_extra_candidate import EXTRA_IDS
    return {'total':len(ids),'menu_probe':len(ids&probed),'configuration_probes':len(ids&EXTRA_IDS),'schedule_preview':len(ids&schedule),
            'disabled':len(ids&disabled),'unprobed':unprobed,
            'unprobed_reasons':{key:UNPROBED_REASONS.get(key,'unclassified') for key in unprobed}}


def app_root(root):
    root=Path(root)
    if (root/'profiles/DKB').is_dir():return root
    candidate=root/'vendor/DKB_Auto'
    if (candidate/'profiles/DKB').is_dir():return candidate
    raise ValueError('프로그램 프로필을 찾지 못했습니다.')

def flatten(value,prefix=''):
    out={}
    for key,item in value.items():
        name=prefix+'.'+key if prefix else key
        if isinstance(item,dict):out.update(flatten(item,name))
        else:out[name]=item
    return out

def load_values(root):
    path=root/'settings/auto-settings.json'
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value,dict):raise ValueError('자동 설정 형식을 확인해 주세요.')
    values=value.get('values')
    if not isinstance(values,dict):raise ValueError('자동 설정 values 항목을 확인해 주세요.')
    return flatten(values)

def inspect_schedule(root,values):
    """Run only the planner's existing read-only preview, with a copied state."""
    import owner_timetable as timetable
    cfg_path=root/'settings/owner-timetable.json'
    state_path=root/'settings/owner-timetable-state.json'
    if not cfg_path.exists() or not state_path.exists():
        return {'verified':False,'detail':'시간표 설정 또는 실행 기록 없음'}
    cfg=json.loads(cfg_path.read_text(encoding='utf-8-sig'))
    data=json.loads(state_path.read_text(encoding='utf-8-sig'))
    if cfg.get('version')!=1 or not isinstance(cfg.get('jobs'),dict) or not cfg.get('seed'):
        raise ValueError('시간표 설정 형식 오류')
    if data.get('version')!=1 or not isinstance(data.get('characters'),dict):
        raise ValueError('시간표 실행 기록 형식 오류')
    for key,row in cfg['jobs'].items():
        if key not in timetable.BY_KEY:continue
        clock=row.get('time',timetable.BY_KEY[key].clock)
        datetime.strptime(clock,'%H:%M')
        jitter=row.get('jitter_seconds',cfg.get('jitter_seconds',60))
        if type(jitter) is not int or not 0<=jitter<=120:raise ValueError('시간표 랜덤 범위 오류')
        days=row.get('weekdays')
        if days is not None and (not isinstance(days,list) or not days or any(type(d) is not int or d not in range(7) for d in days)):
            raise ValueError('시간표 요일 오류')
    class Preview(timetable.Planner):
        def commit(self):pass
    preview=Preview.__new__(Preview);preview.root=root;preview.values=dict(values)
    preview.identity=timetable.identity(root);preview.data=copy.deepcopy(data)
    preview.state=preview.data['characters'].setdefault(preview.identity,{})
    at=timetable.now()
    if 'readonly' in inspect.signature(timetable.Planner.build).parameters:
        preview.build(at,readonly=True)
    else:
        # r20's planner predates its read-only argument and config() may fill
        # defaults on disk. Run the same function against private globals and
        # copied data, replacing only that config provider. Never patch the
        # module used by the actual scheduler or call its commit/save.
        original=inspect.unwrap(timetable.Planner.build)
        namespace=dict(original.__globals__)
        namespace['config']=lambda path:copy.deepcopy(cfg)
        namespace['save']=lambda *args,**kwargs:(_ for _ in ()).throw(RuntimeError('점검 중 설정 저장 금지'))
        build=types.FunctionType(original.__code__,namespace,original.__name__,original.__defaults__,original.__closure__)
        build.__kwdefaults__=original.__kwdefaults__
        build(preview,at)
    pending=sum(r.get('status')=='pending' for r in preview.state.values())
    return {'verified':True,'detail':f'예약 계산 확인 · 대기 {pending}개 · 실행 없음'}

def inspect_contract(root,item,values):
    failures=[];notes=[]
    missing=[key for key in item.get('settings',()) if key not in values]
    setting=('—' if not item.get('settings') else '미설정' if missing else '켜짐' if any(values.get(k) is True for k in item.get('settings',())) else '꺼짐')
    if missing:notes.append('설정 항목 확인 필요: '+', '.join(missing))
    templates=root/'profiles/DKB/templates'
    for name in item.get('templates',()):
        if Path(name).name!=name or not name.endswith('.png'):raise ValueError('점검 이미지 경로 오류')
        path=templates/name
        if not path.is_file():failures.append('이미지 누락: '+name)
        else:
            from PIL import Image
            try:
                from project_adapter import protected_assets
                with Image.open(io.BytesIO(protected_assets.read_bytes(path))) as image:image.verify()
            except Exception:failures.append('이미지 읽기 실패: '+name)
    for module,name in item.get('native',()):
        try:
            target=importlib.import_module(module)
            if not callable(getattr(target,name,None)):failures.append('처리 함수 없음: '+name)
        except Exception as exc:failures.append('처리 모듈 읽기 실패: '+module+' · '+str(exc)[:160])
    row={'id':item['id'],'name':item['name'],'settings':setting,'screen':'미점검',
         'result':'오류' if failures else '확인 필요','detail':' / '.join(failures+notes) or '기본 구성 확인 · 게임 화면 미점검',
         'contract_ok':not failures and not missing,'screen_verified':False,'end_to_end':False}
    row['stage'],row['finding']=_contract_stage(item,failures,missing,setting)
    row['steps']=[{'stage':'settings','status':('off' if setting=='꺼짐' else 'missing' if setting=='미설정' else 'on' if setting=='켜짐' else 'none')},
                  {'stage':'wiring','status':('error' if failures else 'ok')}]
    if item.get('disabled_by_user'):
        row.update(settings='사용 불가',screen='제외',result='확인 필요',detail='사용자 요청으로 사용 불가',
                   stage='unsupported',finding='disabled')
    return row

def _save_report(root,report):
    folder=root/'logs/feature-checks';folder.mkdir(parents=True,exist_ok=True)
    name=datetime.now(KST).strftime('%Y%m%d_%H%M%S_%f')+'.json'
    target=folder/name
    fd,tmp=tempfile.mkstemp(prefix='.check-',suffix='.tmp',dir=str(folder))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(report,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,target)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return str(target)


def attach_projection(root,item,values,row):
    """Non-input checks keep running even after another screen is unknown."""
    from owner_feature_check_extra_candidate import EXTRA_IDS,diagnose
    if item['id'] not in EXTRA_IDS or not row['contract_ok'] or row['stage']=='config':return False
    record=diagnose(item['id'],root=root,values=values)
    row.update(stage=record['stage'],finding=record['finding'],screen='설정·기록 확인',
               result='확인 필요',detail=record['detail'],diagnostic=record,
               screen_verified=False,decision_verified=False,end_to_end=False)
    row['steps'].extend(record['steps'])
    _finish_row(row)
    return True

def _finish_row(row):
    row['verification']=verification(row)
    row['assessment']=assessment(row);row['display_status']=display_status(row)

def run_checks(project_root,selected_ids,emit,cancel_event,probe=None,probe_off=False):
    from owner_feature_check_catalog_candidate import CHECKS
    root=app_root(project_root);items={item['id']:item for item in CHECKS}
    chosen=list(dict.fromkeys(selected_ids))
    if any(key not in items for key in chosen):raise ValueError('알 수 없는 점검 항목')
    started=time.monotonic();rows=[];values=None;settings_error=None;schedule=None;stopped=None
    try:values=load_values(root)
    except (ValueError,OSError) as exc:settings_error=str(exc)
    for key in chosen:
        item=items[key];row=None
        if cancel_event.is_set():
            row={'id':key,'name':item['name'],'settings':'—','screen':'—','result':'중지','detail':'사용자 중지','contract_ok':False,'screen_verified':False,'end_to_end':False,'stage':'skipped','finding':'cancelled'}
            rows.append(row);emit(dict(row));break
        if stopped is not None:
            # Keep the offline contract evidence for the rest of the sweep; only
            # the live stage stays unperformed. A wiring error still surfaces.
            try:
                if settings_error:raise ValueError(settings_error)
                row=inspect_contract(root,item,values)
                if attach_projection(root,item,values,row):
                    rows.append(row);emit(dict(row));continue
                if row['stage'] in ('config','unsupported'):
                    _finish_row(row)
                    rows.append(row);emit(dict(row));continue
                row['steps'].append({'stage':'menu','status':'skipped'})
                contract_detail=row['detail']
                row.update(result='확인 필요',screen='미점검',
                           detail=f"구성 확인됨 · {stopped['id']} 화면 미확인으로 이동 중단 · 실행 없음",
                           screen_verified=False,end_to_end=False,stage='skipped',finding='navigation_stopped')
                if not row['contract_ok']:
                    row.update(result='오류',detail=contract_detail+' · 이동 중단으로 화면 미점검',
                               stage='contract',finding='contract_error')
            except Exception as exc:
                row={'id':key,'name':item['name'],'settings':'확인 필요','screen':'미점검','result':'오류',
                     'detail':str(exc)[:300],'contract_ok':False,'screen_verified':False,'end_to_end':False,
                     'stage':'contract','finding':'contract_error',
                     'steps':[{'stage':'settings','status':'unknown'},{'stage':'wiring','status':'error'}]}
            if stopped.get('evidence_file'):row['evidence_file']=stopped['evidence_file']
            _finish_row(row)
            rows.append(row);emit(dict(row));continue
        try:
            if settings_error:raise ValueError(settings_error)
            row=inspect_contract(root,item,values)
            if attach_projection(root,item,values,row):pass
            elif row['contract_ok'] and not item.get('disabled_by_user') and (probe_off or row['stage']!='config'):
                if item.get('schedule_only'):
                    if schedule is None:schedule=inspect_schedule(root,values)
                    row.update(screen='예약 계산',result='정상' if schedule['verified'] else '확인 필요',
                               detail=schedule['detail'],screen_verified=False,stage='action_ready',finding='schedule_preview')
                    row['steps'].append({'stage':'schedule','status':'computed' if schedule['verified'] else 'unverified'})
                elif callable(probe):
                    observation=probe(item,cancel_event)
                    if not isinstance(observation,dict):raise ValueError('화면 점검 결과 형식 오류')
                    # A menu probe can prove recognition, never the completion
                    # of an enhancement, purchase, dungeon, boss or reward.
                    verified=observation.get('verified') is True
                    decision=observation.get('decision_verified') is True
                    stage,finding=_observation_stage(observation,verified,decision)
                    row.update(screen=observation.get('screen','미점검'),screen_verified=verified,decision_verified=decision,
                               result='정상' if verified and decision else '확인 필요',
                               detail=str(observation.get('detail','화면 확인 필요')),stage=stage,finding=finding,
                               values_verified=observation.get('values_verified') is True)
                    if isinstance(observation.get('targets'),dict):row['targets']=observation['targets']
                    evidence=observation.get('evidence_file')
                    if isinstance(evidence,str):row['evidence_file']=evidence
                    row['steps'].extend(list(observation.get('steps') or []))
                    if observation.get('stop_navigation') is True:
                        stopped={'id':key,'evidence_file':row.get('evidence_file')}
            elif row.get('stage') in ('config','contract'):
                # OFF or a wiring error is the outcome; no live navigation runs.
                row['steps'].append({'stage':'menu','status':'not_probed'})
            if cancel_event.is_set():row.update(result='중지',detail='사용자 중지')
        except Exception as exc:
            if row is None:
                row={'id':key,'name':item['name'],'settings':'확인 필요','contract_ok':False}
            row.update(screen='점검 오류',result='오류',detail=str(exc)[:700],screen_verified=False,end_to_end=False,
                       stage='contract',finding='contract_error')
        _finish_row(row)
        rows.append(row);emit(dict(row))
    report={'version':1,'at':datetime.now(KST).isoformat(),'duration_seconds':round(time.monotonic()-started,3),
            'cancelled':cancel_event.is_set(),'gameplay_execution_tested':False,'rows':rows,
            'stopped_after':copy.deepcopy(stopped),'coverage':coverage(),
            'summary':summarize(rows),'verification_levels':level_counts(rows),'metrics':getattr(probe,'metrics',lambda:{})(),
            'navigation_actions':copy.deepcopy(getattr(probe,'navigation',[]))[:500]}
    report['report_file']=_save_report(root,report)
    return report
