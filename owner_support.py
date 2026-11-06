"""Explicit local-owner execution policy; it never fabricates server credentials."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import math
from pathlib import Path
import threading
import time


class LocalScheduleClock:
    """Schedule-clock compatibility using the PC's time, without a server."""
    def __init__(self,monotonic=time.monotonic,user_log=None,file_log=None):
        self.monotonic=monotonic
        self.user_log=user_log or (lambda text:None)
        self.file_log=file_log or (lambda text:None)
        self.started=False
        self.lock=threading.RLock()
        self._time=datetime.now(timezone(timedelta(hours=9)))
        self._tick=monotonic()

    def start(self):
        if not self.started:
            self.started=True
            self.user_log('예약 시간 기준: 이 PC의 시각 · 원격관제 연결 없음')

    def get_server_datetime(self):
        return self._time+timedelta(seconds=max(0,self.monotonic()-self._tick))

    def get_server_time(self):
        return self.get_server_datetime().timestamp()

    def is_server_time_ready(self):
        return True

    def poll(self):
        return None

    def reset_binding(self,binding):
        return None

    def update(self,value):
        return False


@dataclass(frozen=True)
class LocalPolicyState:
    valid: bool = True
    message: str = '개발용 · 라이선스 인증 없음'
    expires_at: str = ''


class LocalExecutionPolicy:
    def __init__(self, project):
        self.project = project
        self.path = project.root / 'license.dat'
        self.lock = threading.RLock()
        self.result = LocalPolicyState()
        self.offline = False
        self.device_counts = {}
        self.customer_name = '로컬 개발용'
        self.last_failure_kind = ''
        self.binding = None
        self.auth = {}
        self.server_url = ''
        self.identity = {}

    def is_valid(self):
        return True

    def require_valid(self):
        return None

    def verify(self):
        return self.result

    def invalidate(self):
        # Remote-service failures cannot revoke local-owner execution.
        return None

    def credentials(self):
        raise RuntimeError('이 개발용 버전은 BIOL 원격관제에 연결하지 않습니다.')


def authorize(gui, entered_key=None):
    if gui.closed.is_set():
        return
    gui.license = LocalExecutionPolicy(gui.project)
    gui.auth_thread = None
    gui._license_result_received = True
    gui.next_license_refresh = math.inf
    gui.license_state.set(gui.license.result.message)
    gui.manager_state.set('로컬 개발용 · 원격관제 제외')
    gui.project.operations['manager_remote'] = False
    gui.project.operations['manager_local'] = False
    # No successful-authentication event is enqueued: the original tick does
    # not construct a remote Manager, and all game/input readiness gates remain.


def local_caption(gui):
    return '개발용 · 라이선스 인증 없음'


def finish_local_ui(gui):
    """Detach only remote-service presentation from the existing game UI."""
    if gui.closed.is_set():
        return
    import tkinter as tk
    button = getattr(gui, 'log_send_button', None)
    if button is not None:
        button.configure(text='진단 저장')
    stack = [gui.root]
    while stack:
        widget = stack.pop()
        stack.extend(widget.winfo_children())
        try:
            if str(widget.cget('text')) in ('만료일 확인 중', '사용 기간 제한 없음'):
                widget.configure(textvariable='', text='사용 기간 제한 없음')
        except tk.TclError:
            pass
    if '로컬 개발용' not in gui.root.title():
        gui.root.title(gui.root.title() + ' · 로컬 개발용')
    from owner_controls import install
    install(gui)
    from owner_incidents import install as install_incidents
    install_incidents(gui)
    from owner_main import install as install_main
    install_main(gui)
    from owner_performance import install as install_performance
    install_performance(gui)
    from owner_task_flow import install as install_task_flow
    install_task_flow(gui)
    from owner_inventory import install as install_inventory
    install_inventory(gui)
    from owner_coupons import install as install_coupons
    install_coupons(gui)
    from owner_rewards import install as install_rewards
    install_rewards(gui)
    from owner_progression import install as install_progression
    install_progression(gui)
    from owner_routes import install as install_routes
    install_routes(gui)
    from owner_hunt import install as install_hunt
    install_hunt(gui)
    from owner_work_resume import install as install_work_resume
    install_work_resume(gui)
    from owner_town_return import install as install_town_return
    install_town_return(gui)
    from owner_treasure import install as install_treasure
    install_treasure(gui)
    from owner_reconnect import install as install_reconnect
    install_reconnect(gui)
    from owner_quest_tracker import install as install_quest_tracker
    install_quest_tracker(gui)
    from owner_equipment_boxes import install as install_equipment_boxes
    install_equipment_boxes(gui)
    from owner_startup_stage import install as install_startup_stage
    install_startup_stage(gui)
    from owner_diagnostic_repairs import install as install_diagnostic_repairs
    install_diagnostic_repairs(gui)
    from owner_image_scope import install as install_image_scope
    install_image_scope(gui)
    from owner_scene_archive import install as install_scene_archive
    install_scene_archive(gui)
    from owner_quest_watchdog import install as install_quest_watchdog
    install_quest_watchdog(gui)
    from owner_schedule_priority import install as install_priority
    install_priority(gui)
    from owner_boss_gate import install as install_boss_gate
    install_boss_gate(gui)
    from owner_raid_tickets import install as install_raid_tickets
    install_raid_tickets()
    from owner_timetable import install as install_timetable
    install_timetable(gui)
    from owner_restart_memory import install as install_restart_memory
    install_restart_memory(gui)
    from owner_skill_goal import install as install_skill_goal
    install_skill_goal(gui)
    from owner_schedule_ui import install as install_schedule
    install_schedule(gui)
    from owner_membership import install as install_membership
    install_membership(gui)
    from owner_mission_schedule_bridge_candidate import install as install_mission_schedule_bridge
    install_mission_schedule_bridge()
    from owner_mission_controller import install as install_mission_catalog
    install_mission_catalog(gui)
    from owner_album_disabled import install as install_album_disabled
    install_album_disabled(gui)
    # Aggregate only timing/outcome categories; never collect OCR text or images.
    # Diagnostics must not prevent the program from starting if unavailable.
    perf = None; perf_handle = None
    try:
        import owner_mission_ui
        from owner_image_perf_candidate import ImagePerf
        from owner_mission_perf_adapter_candidate import install as install_mission_perf
        perf = ImagePerf(Path(gui.project.root)/'logs/owner-image-performance.jsonl')
        perf_handle = install_mission_perf(owner_mission_ui,perf)
        gui._owner_image_perf = perf_handle
        gui.root.bind('<Destroy>',lambda event: gui._owner_image_perf.close() if event.widget is gui.root else None,add='+')
    except Exception:
        if perf_handle is not None:perf_handle.close()
        elif perf is not None:perf.close(timeout=0)
        gui.logger.exception('임무 인식 성능 기록 연결 실패 · 기본 동작 유지')
    from owner_dialogue import install as install_dialogue
    install_dialogue(gui)
    from owner_seal_shop import install as install_seal_shop
    install_seal_shop(gui)
    from owner_boss_purple import install as install_boss_purple
    install_boss_purple(gui)
    from owner_hunt_settings_candidate import install as install_hunt_settings
    install_hunt_settings(gui)
    from owner_program_runtime import install as install_program_runtime
    install_program_runtime(gui)
    # User retired the menu-only checker. Per-feature TEST uses Session's
    # existing sole worker and the production dispatch instead.
    from owner_storage import install as install_storage
    install_storage(gui)
    from owner_ocr_readiness import install as install_ocr_readiness
    install_ocr_readiness(gui)
    from owner_auto_update import install as install_auto_update
    install_auto_update(gui)


def start_owner_app(job):
    import json
    import subprocess
    app = Path(job['app']).resolve()
    root = app.parent.parent
    manifest = json.loads((app / 'package-manifest.json').read_text(encoding='utf-8-sig'))
    version = manifest['runtime_version']
    if not version or any(c not in '0123456789.' for c in version):
        raise ValueError('Invalid pinned Runtime version')
    executable = app.parent / 'BIOL_Runtime' / version / 'python/pythonw.exe'
    entry = root / 'owner/start.py'
    if not executable.is_file() or not entry.is_file():
        raise FileNotFoundError('개발용 실행 구성요소를 찾지 못했습니다.')
    # Return a parent that remains alive until the GUI exits. The upstream
    # updater can therefore retain its original descendant/readiness checks.
    return subprocess.Popen([str(executable), str(entry)], cwd=str(root), creationflags=0x08000000)
