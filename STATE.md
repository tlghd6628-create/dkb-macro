# dkb-mem 진행 상태

## 환경
- 게임: 도깨비의 세계, dokkaebi.exe (Unity IL2CPP), 안티치트 xhunter2
- 순서: 드라이버 로드 → 게임 실행 (게임 중 로드는 647 실패)
- 부팅: testsigning off + nointegritychecks on + F7 (매 재부팅)
- 창 UnityWndClass, 클라 1366x768, ClientToScreen (6,31), 최소화 시 입력 불가

## 드라이버
- 서비스 MemReaderE, 장치 \\.\MemReaderZ2, 파일 C:\drv\MR8.sys
- IOCTL 0x800 SET_PID / 0x804 GET_BASE / 0x808 READ / 0x80C WRITE / 0x810 MODS
- 소스 C:\drv\MemReader\MemReader\MemReader.c
- 스크립트 mr.ps1 / mr2.ps1(MRS2) / mr3.ps1(MRS3+ScanSet) / probe.ps1 / chain.ps1
- IOCTL 하위 2비트가 11이면 METHOD_NEITHER → SystemBuffer NULL

## 아이템 구조 (확정)
- +0x00 강화 / +0x04 개방 / +0x08 돌파 / +0x0C 각성
- +0x14 정의 포인터, -0x04 아이템 ID, -0x20 1.0f
- 사본 5~6개, 강화 시 전부 해제·재할당 (주소·서명 휘발)
- 사본 쓰기는 2초 내 서버 동기화로 복원됨

## 아이템 찾기
1. MR-Scan <강화값> (2번째 인자 생략)
2. 히트를 16바이트 읽어 +4/+8/+12 일치만 유지
3. +0x14 정의 포인터로 그룹핑, 키가 *AC010000 이고 2개 이상인 최대 그룹이 진짜

## 다음
- chain.ps1 로 상향 탐색 → 장비 배열 → 플레이어 객체 → GameAssembly.dll 고정 주소
- 플레이어 오프셋 맵: 레벨/경험치/스탯/전투력/재화/도술/장비/인벤토리
- 최종 파이썬 매크로 (비활성 PostMessage + 메모리 읽기)

## 범위
착용 장비, 인벤토리, 도술, 레벨/경험치, 전투력/스탯, 재화
