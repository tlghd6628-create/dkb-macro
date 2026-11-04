"""Moved and re-rendered UI, using real saved frames and fake inputs. Never a game test."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bootstrap
import shutil,threading,unittest
from types import SimpleNamespace as S
from unittest.mock import patch
import numpy as np
from PIL import Image
from roi_runtime import RoiDetector
from biol_base.session import Context
import owner_image_scope as scope
scope.install()
import owner_movement as m
import owner_startup_stage as st
from owner_special_contexts import NAMES
from project_adapter.secret_exploration import AUTO_NAMES
from project_adapter.sleep_mode import SleepModeActions
import project_adapter.town_services as town

F=Path(__file__).resolve().parent/'fixtures_image_scope'
def load(name):return np.array(Image.open(F/(name+'.png')).convert('RGB'))
MODAL_NEW,MAP_NEW,PLAIN_NEW,EVENT_NEW='modal_new','map_new','plain_new','event_new'
MODAL_OLD,FIELD_OLD='modal_old','field_old'
PROFILE=bootstrap.A/'profiles/DKB'
TELEPORT='버튼_축지술_가운데';MAP_BTN='버튼_지도_축지술';BOSS_BTN='버튼_보스_축지술'

class Cap:
    def __init__(self,get):self.get=get
    def __call__(self):return self.get()
    def __getattr__(self,n):return lambda *a,**k:True
class Inputs:
    def __init__(self,log=None,name='inputs'):self.log=log if log is not None else [];self.name=name
    def __getattr__(self,n):return Inputs(self.log,self.name+'.'+n)
    def __call__(self,*a,**k):
        if not self.name.endswith('require_ready'):self.log.append((self.name,a,k))
        return self
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def __bool__(self):return True

class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=RoiDetector(PROFILE,[TELEPORT,MAP_BTN,BOSS_BTN,'버튼_귀환','버튼_전체매뉴','버튼_성장_장비탭','체크_성장','버튼_성장_장비_강화버튼'])
        cls.frames={n:load(n) for n in (MODAL_NEW,MAP_NEW,PLAIN_NEW,EVENT_NEW,MODAL_OLD,FIELD_OLD)}

class Windows(Base):
    def test_real_modal_button_found_at_new_spot(self):
        hit=self.d.find(TELEPORT,self.frames[MODAL_NEW]);self.assertEqual(hit[:2],(403,306))
    def test_real_map_buttons_found_at_new_spot(self):
        self.assertEqual(self.d.find(MAP_BTN,self.frames[MAP_NEW])[2][:2],(767,447))
        self.assertEqual(self.d.find(BOSS_BTN,self.frames[MAP_NEW])[2][:2],(764,447))
    def test_old_layout_still_uses_exact_match(self):
        self.assertEqual(self.d.find(TELEPORT,self.frames[MODAL_OLD])[2][:2],(433,299))
    def test_no_window_means_no_search(self):
        self.assertIsNone(self.d.find(TELEPORT,self.frames[PLAIN_NEW]))
        self.assertIsNone(self.d.find(MAP_BTN,self.frames[PLAIN_NEW]))
    def test_other_window_button_is_not_borrowed(self):
        # The map's 축지술 must not satisfy the modal image, nor the reverse.
        self.assertIsNone(self.d.find(TELEPORT,self.frames[MAP_NEW]))
        self.assertIsNone(self.d.find(MAP_BTN,self.frames[MODAL_NEW]))
    def test_two_equal_buttons_are_rejected(self):
        f=self.frames[MODAL_NEW].copy();f[301:312,467:499]=f[301:312,387:419]
        self.assertIsNone(self.d.find(TELEPORT,f))
    def test_real_neighbour_alone_is_not_taken(self):
        # Hide 축지술: only 축지부 사용 remains, and it must not be clicked.
        f=self.frames[MODAL_NEW].copy();f[301:312,387:419]=f[301,380]
        self.assertIsNone(self.d.find(TELEPORT,f))
    def test_low_threshold_callers_stay_on_the_raw_score(self):
        self.assertIsNone(self.d.find(MAP_BTN,self.frames[PLAIN_NEW],threshold=.5))
    def test_candidate_filter_still_decides(self):
        self.assertIsNone(self.d.find(TELEPORT,self.frames[MODAL_NEW],candidate_filter=lambda f,h:False))
    def test_shifted_member_moves_only_inside_its_window(self):
        f=self.frames[MODAL_NEW]
        self.assertFalse(scope.window_open(PROFILE,'growth',f))
    def test_commit_buttons_never_relocate(self):
        e=self.d.entries['버튼_성장_장비_강화버튼'];x,y,w,h=e['x'],e['y'],e['w'],e['h']
        f=self.frames[FIELD_OLD].copy();f[y:y+h,x-40:x-40+w]=self.d.templates['버튼_성장_장비_강화버튼'][:,:,::-1]
        self.assertTrue(scope.committed('버튼_성장_장비_강화버튼'))
        self.assertIsNone(self.d.find('버튼_성장_장비_강화버튼',f))
    def test_commit_list_covers_spending_names(self):
        for name in ('버튼_물약상인_구매','버튼_레이드_매칭','버튼_레이드_일괄소모','버튼_인벤토리_상자열기','버튼_성장_장비_각성실행','버튼_성장_장비_돌파실행','버튼_임무_일일_즉시완료1','버튼_가호_소환10','버튼_인벤토리_지금분해'):
            self.assertTrue(scope.committed(name),name)
    def test_window_members_are_not_commit_except_named_teleports(self):
        allowed={TELEPORT,MAP_BTN,BOSS_BTN}
        for key,window in scope.WINDOWS.items():
            for name in window['members']:
                if name not in allowed:self.assertFalse(scope.committed(name),name)

class StateSlots(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=RoiDetector(PROFILE,list(scope.SLOT_OF))
        cls.raid=load('raid_stage1')
    def test_each_real_stage_screen_reads_only_its_own_stage(self):
        for shown in (1,2,3,4,5):
            frame=load('raid_stage%d'%shown)
            for n in (1,2,3,4,5):
                hit=self.d.find('체크_레이드_%d단계'%n,frame,threshold=.95)
                self.assertEqual(hit is not None,n==shown,(shown,n))
    def test_absent_slot_reads_nothing(self):
        for n in (1,2,3,4,5):self.assertIsNone(self.d.find('체크_레이드_%d단계'%n,load('plain_new')),n)
    def test_the_native_raid_call_is_covered(self):
        # The original flow asks at .95; the slot comparison is what proves the stage.
        self.assertIsNotNone(self.d.find('체크_레이드_1단계',self.raid,threshold=.95))
    def test_stricter_callers_keep_the_exact_rule(self):
        self.assertIsNone(self.d.find('체크_레이드_1단계',self.raid,threshold=.97))

class Tower(unittest.TestCase):
    def test_real_tower_floors_are_recognised(self):
        for n in ('tower_floor_a','tower_floor_b'):self.assertTrue(m.tower_combat(load(n)),n)
    def test_tower_menu_and_field_are_not_combat(self):
        for n in ('tower_menu','plain_new','raid_stage1'):self.assertFalse(m.tower_combat(load(n)),n)
    def test_scene_says_tower_inside_the_tower(self):
        d=RoiDetector(PROFILE,list(dict.fromkeys([st.DUNGEON,st.EXIT,st.MENU,*AUTO_NAMES,*NAMES])))
        self.assertEqual(st.scene(d,load('tower_floor_a')),'tower_combat')

class Redrawn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.d=RoiDetector(PROFILE,['버튼_레이드_다음단계','체크_비경_기본시간','체크_비경_추가시간'])
    def test_reworded_dungeon_time_labels_are_found(self):
        frame=load('dungeon_daily')
        for name in ('체크_비경_기본시간','체크_비경_추가시간'):
            e=self.d.entries[name];hit=self.d.find(name,frame,threshold=.95)
            self.assertIsNotNone(hit,name)
            self.assertEqual((hit[2][2]-hit[2][0],hit[2][3]-hit[2][1]),(e['w'],e['h']));self.assertLessEqual(abs(hit[2][1]-e['y']),2)
    def test_time_labels_stay_out_of_other_windows(self):
        for n in ('plain_new','mail_open','raid_stage1','mission_fresh'):
            for name in ('체크_비경_기본시간','체크_비경_추가시간'):self.assertIsNone(self.d.find(name,load(n)),(n,name))
    def test_new_arrow_is_found_in_the_raid_window(self):
        hit=self.d.find('버튼_레이드_다음단계',load('raid_stage1'));self.assertIsNotNone(hit)
        self.assertTrue(868<=hit[0]<=881 and 89<=hit[1]<=108)
    def test_not_found_outside_the_window(self):
        for n in ('plain_new','mission_fresh','map_new'):self.assertIsNone(self.d.find('버튼_레이드_다음단계',load(n)),n)

class Options(unittest.TestCase):
    def model(self,parent_on):
        def editable(item):return not item.get('enabled_if') or parent_on
        return S(editable=editable)
    def test_test_row_options_stay_open_with_the_switch_off(self):
        from owner_settings_console import option_editable
        self.assertTrue(option_editable(self.model(False),{'id':'auto_schedule.boss_raid.stage','enabled_if':'auto_schedule.boss_raid.enabled'}))
    def test_other_dependent_options_still_follow_their_switch(self):
        from owner_settings_console import option_editable
        self.assertFalse(option_editable(self.model(False),{'id':'x','enabled_if':'common.skill_preset.enabled'}))

class NativeFlow(Base):
    def test_native_detect_and_guarded_click_use_the_new_spot(self):
        log=[];context=Context(threading.Event(),threading.Event())
        frame=[self.frames[MODAL_NEW]]
        actions=SleepModeActions(self.d,Cap(lambda:frame[0]),context,Inputs(log))
        hit=actions.detect(TELEPORT,timeout=.1);self.assertEqual(hit[:2],(403,306))
        actions.click(TELEPORT,hit,pre_wait=0)
        call=[row for row in log if row[0]=='inputs.click'];self.assertEqual(len(call),1);self.assertEqual(call[0][1],(403,306))
        guard=call[0][2]['before_down'];guard()
    def test_input_guard_rejects_a_window_that_closed(self):
        log=[];context=Context(threading.Event(),threading.Event());frame=[self.frames[MODAL_NEW]]
        actions=SleepModeActions(self.d,Cap(lambda:frame[0]),context,Inputs(log))
        hit=actions.detect(TELEPORT,timeout=.1)
        actions.click(TELEPORT,hit,pre_wait=0)
        guard=[row for row in log if row[0]=='inputs.click'][0][2]['before_down']
        frame[0]=self.frames[PLAIN_NEW]
        with self.assertRaises(BaseException):guard()
    def test_native_map_travel_click_finds_the_moved_button(self):
        # 14:36 real failure: the native click reads through StateROIs.match_roi, not find.
        from project_adapter import favorite_hunt
        log=[];context=Context(threading.Event(),threading.Event())
        actions=SleepModeActions(self.d,Cap(lambda:self.frames[MAP_NEW]),context,Inputs(log))
        favorite_hunt.click_travel(actions)
        call=[row for row in log if row[0]=='inputs.click'];self.assertEqual(len(call),1)
        self.assertEqual(call[0][1][1],451)
    def test_native_map_travel_click_refuses_a_plain_field(self):
        from project_adapter import favorite_hunt
        log=[];context=Context(threading.Event(),threading.Event())
        actions=SleepModeActions(self.d,Cap(lambda:self.frames[PLAIN_NEW]),context,Inputs(log))
        with self.assertRaises(RuntimeError):favorite_hunt.click_travel(actions)
        self.assertEqual([row for row in log if row[0]=='inputs.click'],[])
    def test_second_path_keeps_unmapped_names_exact(self):
        from project_adapter.main_quest import StateROIs
        slots=S(detector=self.d,size=(897,479));name='버튼_귀환'
        self.assertNotIn(name,scope.MEMBER)
        with patch.object(scope,'recover',side_effect=AssertionError('must not recover')):
            self.assertIsNone(StateROIs.match_roi(slots,name,self.frames[MAP_NEW],{'threshold':.9})['hit'])
    def test_second_path_keeps_diagnostic_override_raw(self):
        from project_adapter.main_quest import StateROIs
        slots=S(detector=self.d,size=(897,479))
        result=StateROIs.match_roi(slots,MAP_BTN,self.frames[MAP_NEW],{'threshold':.9},threshold_override=.9)
        self.assertIsNone(result['hit'])
    def test_original_town_return_passes_on_real_frames(self):
        calls=[];current=[self.frames[PLAIN_NEW]];frames=self.frames
        class Replay(town.TownServices):
            def __init__(self,adapter,c,inputs,names):
                super().__init__(adapter,c,inputs,names)
                self.capture=Cap(lambda:current[0]);self.actions.capture=self.capture
            def key(self,code):
                calls.append(('key',code))
                if code==36:current[0]=frames[MODAL_NEW]
            def click_hit(self,hit):
                calls.append(('click',hit[:2]));current[0]=frames[PLAIN_NEW]
            def wait_menu(self,*a,**k):return True
            def wake(self):pass
        adapter=S(project=S(root=bootstrap.A,code='DKB',app_id='DKB'),values={},mode='sub_quest',window=None,status=None)
        with patch.object(town,'TownServices',Replay):result=town.run_town_return(adapter,Context(threading.Event(),threading.Event()),Inputs())
        self.assertTrue(result);self.assertEqual(calls,[('key',36),('click',(403,306))])

class Owner(Base):
    def test_method_window_on_both_layouts(self):
        new=m.method_window(self.frames[MODAL_NEW]);old=m.method_window(self.frames[MODAL_OLD])
        self.assertEqual(new['title'],(399,153));self.assertEqual(new['button'],(378,296));self.assertEqual(new['close'],(538,160))
        self.assertEqual(old['title'],(399,157));self.assertEqual(old['button'],(424,294));self.assertEqual(old['close'],(538,164))
    def test_choice_false_elsewhere(self):
        for n in (MAP_NEW,PLAIN_NEW,EVENT_NEW,FIELD_OLD):self.assertFalse(m.choice(self.frames[n]),n)
    def test_field_hud_tracks_dim_not_absolute_brightness(self):
        self.assertTrue(m.field_hud(self.frames[PLAIN_NEW]));self.assertTrue(m.field_hud(self.frames[FIELD_OLD]))
        for n in (MODAL_NEW,EVENT_NEW,MODAL_OLD,MAP_NEW):self.assertFalse(m.field_hud(self.frames[n]),n)
    def test_scene_reads_open_window_as_not_field(self):
        d=RoiDetector(PROFILE,list(dict.fromkeys([st.DUNGEON,st.EXIT,st.MENU,*AUTO_NAMES,*NAMES])))
        self.assertEqual(st.scene(d,self.frames[PLAIN_NEW]),'field')
        for n in (MODAL_NEW,EVENT_NEW):self.assertEqual(st.scene(d,self.frames[n]),'unknown',n)
    def test_exact_hud_rule_still_passes_over_bright_scenery(self):
        # Bright scenery behind the translucent icon sinks the shape score; the exact rule remains.
        self.assertTrue(m.field_hud(load('bright_field_old')))
    def test_modal_over_bright_scenery_is_still_a_window(self):
        d=RoiDetector(PROFILE,list(dict.fromkeys([st.DUNGEON,st.EXIT,st.MENU,*AUTO_NAMES,*NAMES])))
        self.assertEqual(st.scene(d,load('modal_bright_new')),'unknown')
    def test_close_click_follows_the_window(self):
        clicks=[];frames=self.frames
        ui=S(frame=lambda:frames[MODAL_NEW],context=S(wait=lambda s:None),rows=lambda *a,**k:[{'text':'거리 : 5m','score':.999}],
             click=lambda x,y,proof:clicks.append((x,y,proof(frames[MODAL_NEW]))),key=lambda k:self.fail('no B under 200m'))
        self.assertFalse(m.confirm_choice(ui));self.assertEqual(clicks,[(538,160,True)])
    def test_second_b_needs_real_distance(self):
        keys=[];frames=self.frames;current=[frames[MODAL_NEW]]
        def key(k):keys.append(k);current[0]=frames[PLAIN_NEW]
        def wait(pred,seconds=5):
            self.assertTrue(pred(current[0]));return current[0]
        ui=S(frame=lambda:current[0],context=S(wait=lambda s:None),rows=lambda *a,**k:[{'text':'거리 : 558m','score':.999}],
             click=lambda *a:self.fail('no close'),key=key,wait=wait)
        self.assertTrue(m.confirm_choice(ui));self.assertEqual(keys,[0x42])
    def test_distance_ignores_cost_rows(self):
        ui=S(rows=lambda *a,**k:[{'text':'500','score':.999},{'text':'거리 : 1,210m','score':.999}])
        self.assertEqual(m.method_distance(ui,{'title':(399,153)}),1210)

class Drift(Base):
    def test_report_says_where_it_went_and_sends_nothing(self):
        out=bootstrap.T/'test_scratch/no-drift-log';shutil.rmtree(out,ignore_errors=True);(out/'profiles/DKB').mkdir(parents=True);(out/'logs').mkdir()
        fake=S(templates=self.d.templates,entries=self.d.entries,profile=out/'profiles/DKB')
        scope.drift_scan.last={}
        row=scope.drift_scan(fake,TELEPORT,self.frames[MODAL_NEW]);self.assertEqual(row['found'],[387,301]);self.assertEqual(row['roi'],[433,299])
        self.assertTrue((out/'logs/image-drift.jsonl').exists())
        self.assertIsNone(scope.drift_scan(fake,TELEPORT,self.frames[MODAL_NEW]))

if __name__=='__main__':unittest.main()
