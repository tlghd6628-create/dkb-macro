"""What the main window's log shows. The log file is not touched: every line is still written there."""
import re

# Preparation steps and routine checks that say nothing about what the program is doing for the player.
HIDDEN=re.compile('|'.join((
 r'준비 완료',r'준비 종료',r'준비 ·',r'연결 ·',r'자동 연결 완료',r'실행 연결',
 r'현재 적용 버전',r'업데이트 확인',r'예약 시간 기준',
 r'세부설정 (?:열기|상태|창)',r'OCR 초기화',r'Paddle',
 r'화면 자료 저장',r'진행 진단 저장',r'이미지 변화 기록',r'개인용 ',
 r'정보창 열림',r'퀘스트 조건 확인',r'캐릭터 정보 확인',r'상태판정',
 r'인벤토리 원격 잡화상점 확인',r'^\s*(?:\d\d:\d\d:\d\d\s*)?완료\s*$',
)))


def hidden(text):
    return bool(HIDDEN.search(text)) if isinstance(text,str) else False


def install(widget):
    """Wraps one Text widget's insert. Safe to call again on the same widget."""
    if getattr(widget,'_owner_log_view',False):return
    original=widget.insert
    def insert(index,text,*rest):
        if hidden(text):return None
        return original(index,text,*rest)
    widget.insert=insert
    widget._owner_log_view=True
