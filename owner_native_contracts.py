"""Shared native definitions for runtime and non-committing diagnostics.

Only immutable detector/profile data is cached, on the owning TownServices
instance. No frames, character readings, action decisions or input are cached.
All region names and alternate energy entries come from the original modules.
"""
from pathlib import Path
import time,copy


class NativeContractError(ValueError):pass

def menu_aliases():
    """Original matching primary/alternate pairs; no cross-menu fallback."""
    from project_adapter import guide_rewards as native
    return {primary:tuple(dict.fromkeys((primary,alternate)))
            for primary,alternate in zip(native.ENTRY_BUTTONS,native.ENTRY_ALTERNATES)}

def menu_candidates(name):
    return menu_aliases().get(name,(name,))

def menu_regions():
    from project_adapter import guide_rewards as native
    return (native.ENTRY_RANGE,)

def find_menu_target(detector,name,frame):
    if any(name in group for group in menu_aliases().values()):
        from project_adapter import guide_rewards as native
        # Use original profile search range and RoiDetector's native default,
        # rather than the checker's added .95 gate at a stale fixed position.
        return detector.find(name,frame,region=native.ENTRY_RANGE)
    return detector.find(name,frame,threshold=.95)


def energy_contract(native=None):
    if native is None:
        from project_adapter import achievement_rewards as native
    return {'entries':(native.ENERGY_ENTRY,native.ENERGY_ENTRY2),'check':native.ENERGY_CHECK,
            'names':tuple(dict.fromkeys((native.ENERGY_ENTRY,native.ENERGY_ENTRY2,native.ENERGY_CHECK,
                 native.ENERGY_ACTIVE,native.ENERGY_INACTIVE,native.ENERGY_BREAKTHROUGH,*native.ENERGY_TABS)))}


def region_names(role,*,module=None):
    if role=='energy':return energy_contract(module)['names']
    from project_adapter import market_inventory as native
    if role=='gear':return tuple(dict.fromkeys((*native.GROWTH_ENHANCE_NAMES,*native.GROWTH_EXEC_BUTTONS)))
    if role=='blessing':return tuple(dict.fromkeys((*native.GROWTH_BLESSING_NAMES,*native.GROWTH_BLESSING_EXEC_BUTTONS)))
    if role=='gear_extra':
        from project_adapter import growth_equipment_extra as extra
        return tuple(dict.fromkeys((*region_names('gear'),extra.AWAKE_TAB,extra.AWAKE_BUTTON,
                                   extra.BREAK_TAB,extra.BREAK_BUTTON,extra.BREAK_RANGE)))
    raise NativeContractError('알 수 없는 판독 범위: '+str(role))


class DetectorPool:
    def __init__(self,profile,*,factory=None):
        self.profile=Path(profile).resolve();self.factory=factory;self.cache={}
        self.loads=0;self.hits=0;self.load_ms=0.
    def get(self,role):
        names=region_names(role);key=(role,names)
        if key in self.cache:self.hits+=1;return self._view(self.cache[key])
        if self.factory is None:
            from roi_runtime import RoiDetector
            factory=RoiDetector
        else:factory=self.factory
        started=time.perf_counter()
        try:detector=factory(self.profile,list(names))
        except (KeyError,OSError,ValueError) as exc:
            raise NativeContractError(f'{role} 원본 판독 정의를 읽지 못했습니다: {exc}') from exc
        missing=set(names)-set(detector.entries)
        if missing:raise NativeContractError(f'{role} 필수 화면 영역 누락: '+', '.join(sorted(missing)))
        self.load_ms+=(time.perf_counter()-started)*1000;self.loads+=1;self.cache[key]=detector
        return self._view(detector)
    @staticmethod
    def _view(prototype):
        # Never lend the cached prototype to a scene handler. Its activity
        # hints or last-match fields must not survive the next borrower.
        view=copy.copy(prototype)
        for field in ('entries','target','templates','masks'):
            value=getattr(prototype,field,None)
            if isinstance(value,dict):setattr(view,field,copy.deepcopy(value) if field in ('entries','target') else dict(value))
        return view
    def snapshot(self):
        return {'loads':self.loads,'cache_hits':self.hits,'load_ms':round(self.load_ms,3)}


def pool_for(service):
    profile=(Path(service.adapter.project.root)/'profiles/DKB').resolve()
    pool=getattr(service,'_owner_native_detector_pool',None)
    if pool is None or pool.profile!=profile:
        pool=DetectorPool(profile);service._owner_native_detector_pool=pool
    return pool


def find_energy_entry(detector,frame,*,module=None):
    return next((name for name in energy_contract(module)['entries'] if detector.find(name,frame,threshold=.95)),None)


def validate_feature(service,key):
    roles={'gear':'gear','gear_enhance':'gear','gear_break':'gear_extra','gear_awaken':'gear_extra',
           'blessing_growth':'blessing','energy':'energy'}
    if key in roles:pool_for(service).get(roles[key])
