"""Leave the field boss area by its own words once the result handler has waited long enough.

pc1 11-06 21:05-21:07: after the boss died the native result handler logged '보상 정리·퇴장 재확인 · 마을귀환 보류'
every minute and never pressed the exit; pressing 나가기 under the minimap and 확인 on '필드 보스 지역에서
퇴장하시겠습니까?' ended it at once. The handler is given this context, and while it waits the exit is tried every
15 s from 90 s on. Nothing else in the handler changes.
"""
import logging,time
LOG=logging.getLogger('project_gui.DKB')
EXIT_WORD=(5,140,75,40)        # real: 나가기 under the minimap
QUESTION=(520,350,330,60)      # real: 필드 보스 지역에서 퇴장하시겠습니까?
CONFIRM=(680,420,150,50)       # real: 확인
AFTER=90;EVERY=15


def words(frame,box):
    import owner_text as text
    return [dict(row,word=text.clean(row['text'])) for row in text.read(None,frame,box,scale=2,minimum=.55)]


def press_exit(service,context):
    """True when the exit question was answered."""
    import owner_hd as hd
    frame=service.capture()
    if getattr(frame,'hi',None) is None:return False
    rows=[r for r in words(frame,EXIT_WORD) if '나가기' in r['word']]
    if len(rows)!=1:return False
    service.click_hit(hd.real_hit(round(rows[0]['rx']),round(rows[0]['ry'])-18));context.wait(1.2)
    frame=service.capture()
    if not any('퇴장' in r['word'] for r in words(frame,QUESTION)):return False
    ok=[r for r in words(frame,CONFIRM) if r['word']=='확인']
    if len(ok)!=1:return False
    service.click_hit(hd.real_hit(round(ok[0]['rx']),round(ok[0]['ry'])));context.wait(1.5)
    LOG.info('필드 보스 퇴장 · 나가기·확인 글자로 누름')
    return True


class Leaving:
    """The ordinary context, whose waits also try the exit after AFTER seconds."""
    def __init__(self,context,service):
        self._context,self._service=context,service;self._since=time.monotonic();self._tried=-1e9;self._busy=False
    def __getattr__(self,name):return getattr(self._context,name)
    def wait(self,seconds):
        now=time.monotonic()
        if not self._busy and now-self._since>=AFTER and now-self._tried>=EVERY:
            self._tried=now;self._busy=True
            try:press_exit(self._service,self._context)
            except Exception as exc:
                from biol_base.session import Cancelled
                if isinstance(exc,Cancelled):raise
                LOG.info('필드 보스 퇴장 시도 보류 · %s',str(exc)[:80])
            finally:self._busy=False
        return self._context.wait(seconds)
