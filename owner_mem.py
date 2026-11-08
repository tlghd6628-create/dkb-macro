"""Worn gear values read straight from memory."""
import ctypes, ctypes.wintypes as w, subprocess

GENERIC_RW = 0xC0000000
IOCTL_SET_PID = 0x800
IOCTL_READ = 0x808
SLOT_INDEX = {'다리': 3, '신발': 4, '장갑': 5, '무기': 7, '반지': 8,
              '목걸이': 9, '팔찌': 10, '귀걸이': 11, '투구': 0, '갑옷': 1, '허리띠': 2}
KLASS_LO = 0x68EDB18
KLASS_HI = 0x362
ENTRY = 0x20
VALUE = 0x18
ENHANCE = 0x38
EXP = 0x40
OPENING = 0x48
BREAK = 0x4C
AWAKEN = 0x50

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.CreateFileW.restype = ctypes.c_void_p
k32.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, ctypes.c_void_p]
k32.DeviceIoControl.restype = ctypes.c_bool
k32.DeviceIoControl.argtypes = [ctypes.c_void_p, w.DWORD, ctypes.c_void_p, w.DWORD, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p]
k32.OpenProcess.restype = ctypes.c_void_p
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]

class MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', w.DWORD), ('RegionSize', ctypes.c_size_t),
                ('State', w.DWORD), ('Protect', w.DWORD), ('Type', w.DWORD)]

def _pid(name='dokkaebi.exe'):
    out = subprocess.check_output(['tasklist', '/FI', 'IMAGENAME eq ' + name, '/FO', 'CSV', '/NH']).decode('cp949', 'ignore')
    return int(out.split(',')[1].strip('"'))

class _Dev:
    def __init__(self):
        h = k32.CreateFileW(r'\\.\MemReaderZ2', GENERIC_RW, 3, None, 3, 0, None)
        if h in (None, ctypes.c_void_p(-1).value):
            raise OSError('device open failed')
        self.h = h
        self.pid = _pid()
        buf = (ctypes.c_ubyte * 16)()
        ctypes.memmove(buf, ctypes.byref(ctypes.c_uint32(self.pid)), 4)
        ret = w.DWORD(0)
        if not k32.DeviceIoControl(ctypes.c_void_p(self.h), IOCTL_SET_PID, buf, 16, buf, 16, ctypes.byref(ret), None):
            raise OSError('SETPID failed')
        self.hp = k32.OpenProcess(0x410, False, self.pid)

    def read(self, addr, size):
        inp = (ctypes.c_ubyte * 16)()
        ctypes.memmove(inp, ctypes.byref(ctypes.c_uint64(addr)), 8)
        ctypes.memmove(ctypes.byref(inp, 8), ctypes.byref(ctypes.c_uint32(size)), 4)
        out = (ctypes.c_ubyte * size)()
        ret = w.DWORD(0)
        if not k32.DeviceIoControl(ctypes.c_void_p(self.h), IOCTL_READ, inp, 16, out, size, ctypes.byref(ret), None):
            return None
        if ret.value == 0:
            return None
        return bytes(out[:ret.value])

    def ok(self, addr, size):
        if not self.hp:
            return True
        m = MBI()
        if not k32.VirtualQueryEx(ctypes.c_void_p(self.hp), ctypes.c_void_p(addr), ctypes.byref(m), ctypes.sizeof(m)):
            return False
        if m.State != 0x1000:
            return False
        end = (m.BaseAddress or 0) + m.RegionSize
        return addr + size <= end

_dev = None
_table = None

def _device():
    global _dev
    if _dev is None:
        _dev = _Dev()
    return _dev

def _u64(b, o):
    return int.from_bytes(b[o:o + 8], 'little')

def _i32(b, o):
    return int.from_bytes(b[o:o + 4], 'little', signed=True)

def _find_table(d):
    addr = 0x10000
    while addr < 0x7FFFFFFFFFFF:
        m = MBI()
        if not k32.VirtualQueryEx(ctypes.c_void_p(d.hp), ctypes.c_void_p(addr), ctypes.byref(m), ctypes.sizeof(m)):
            break
        base = m.BaseAddress or 0
        size = m.RegionSize or 0
        if size == 0:
            break
        if m.State == 0x1000 and (m.Protect & 0xFF) in (4, 8, 0x20, 0x40, 0x80) and size >= 0x1000:
            cur = base
            end = base + size
            while cur < end:
                chunk = min(0x100000, end - cur)
                data = d.read(cur, chunk)
                if data:
                    i = 0
                    while True:
                        i = data.find(KLASS_LO.to_bytes(4, 'little'), i)
                        if i < 0:
                            break
                        if data[i + 4:i + 8] == KLASS_HI.to_bytes(4, 'little'):
                            cand = cur + i
                            head = d.read(cand, 0x20)
                            if head and _u64(head, 0x18) == 12:
                                probe = d.read(cand + 0x20 + ENTRY * 8 + 8, 8)
                                if probe and _u64(probe, 0) >> 32 == 0xE35FA932:
                                    return cand + 0x20
                        i += 4
                cur += chunk
        addr = base + size
    return None

TABLE_HINT = 0x2386E4D98E0

def _table_addr(d):
    global _table
    global _table
    if _table is None:
        head = d.read(TABLE_HINT - 0x20, 0x20)
        if head and _u64(head, 0x18) == 12:
            _table = TABLE_HINT
        else:
            _table = _find_table(d)
    return _table

def values(slot):
    idx = SLOT_INDEX.get(slot)
    if idx is None:
        return None
    try:
        d = _device()
    except OSError:
        return None
    for _ in range(2):
        base = _table_addr(d)
        if base is None:
            return None
        entry = base + ENTRY * idx
        if not d.ok(entry, ENTRY):
            continue
        raw = d.read(entry, ENTRY)
        if not raw:
            continue
        ptr = _u64(raw, VALUE)
        if ptr < 0x10000 or not d.ok(ptr, 0x60):
            continue
        q = d.read(ptr, 0x60)
        if not q:
            continue
        return {'enhance': _i32(q, ENHANCE), 'exp': int.from_bytes(q[EXP:EXP + 8], 'little'),
                'opening': _i32(q, OPENING), 'breakthrough': _i32(q, BREAK), 'awaken': _i32(q, AWAKEN),
                'did': _i32(q, 0x18)}
    global _table
    _table = None
    return None

def level(slot):
    v = values(slot)
    return None if v is None else v['enhance']


import threading, time as _time
_watch = {'stop': False, 'hook': None, 'last': {}}

def watch(hook, seconds=1.0):
    """Call hook(slot, values) whenever a worn slot's values change."""
    _watch['hook'] = hook
    if _watch.get('thread') and _watch['thread'].is_alive():
        return
    def run():
        while not _watch['stop']:
            for slot in SLOT_INDEX:
                v = values(slot)
                if v is None:
                    continue
                if _watch['last'].get(slot) != v:
                    _watch['last'][slot] = v
                    try:
                        _watch['hook'](slot, v)
                    except Exception:
                        pass
            _time.sleep(seconds)
    _watch['thread'] = threading.Thread(target=run, daemon=True)
    _watch['thread'].start()

def unwatch():
    _watch['stop'] = True


_grades = {}

def remember_grade(slot, grade):
    if grade:
        _grades[slot] = grade

def grade(slot):
    return _grades.get(slot)
