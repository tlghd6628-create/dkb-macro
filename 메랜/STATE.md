# 메랜 진행 상태

## 규칙
- 사용자=조작자(모든 PowerShell 실행). Venice=설계·검토·빌드·테스트. GPT=리뷰 전용, 산출물 요구 금지.
- 넘길 때는 "소스 N~M행 + 증상 + 판정할 질문"만. "빌드해서 파일 달라"는 하지 않는다.
- 빌드·매핑·테스트는 로컬. build.ps1·하니스는 저장소 밖.
- Codex 판정도 틀린다. tgt 일치 요구가 크래시 원인이었다.
- 재시작 제어 제외. 게임 중 메모리 쓰기 금지. 게임 중 재매핑 금지. 적재는 드라이버 먼저. testsigning은 off.
- 입력: VK 47개 화이트리스트, down-up 최소 30ms, 입력 간 80ms, 3초 무입력 전체 해제.
- 게이트 4개 유지: 쓰기 전 포그라운드 재확인 / 전체 중립 해제 / 구조 콘솔 CLI / 포커스 이탈 시 폐기+중립+무장해제.
- 주장 금지: 드라이버 타이밍, 물리 콜드/재시작, 사망·맵 무효화, 실제 입력 전달, 런타임 HP, MOB_VERIFIED(0), 후보 20종=몹, 423=개체수, 히트박스·LOS, 패치 검증, AC 탐지.

## 워크오더 형식
    [REVIEW] mslc.sys — <증상 한 줄>
    환경/빌드: <바이트 수, 디바이스 이름>
    첨부: mslc.c N~M행
    질문: 1) ... 2) ...
    산출물 요구 없음

## 개요
메이플랜드 메모리 전용 매크로. 캡처·이미지 인식 없음. msw.exe(Unity x64), 루트 C:\mapland, AC는 BlackCat1.sys 계열.
현재: 읽기 검증 완료, 입력 미검증. 마지막 재부팅으로 매핑 소멸.

## 연혁
이관 문서 계약은 IOCTL_INPUT 0x00222004 {Vk,Up} 하나뿐.
Stage A로 UpperFilters·서비스·testsigning 정리(붙여넣기 잘림, admin 오판, UF 자동복귀, BOM으로 지연). Stage B 통과 후 게임 자가종료 해소.
kdu 부재로 소스 빌드(v145 없음→v143). 스텁으로 4D 5A 확인, INPUT은 쓰레기.
PID 18344, 콜드탐색 1차 중단 후 재시도 성공. GENERATION_MISMATCH → 새 actor_plan(액터 15)로 맵 복구.
300초 소크 2792 NORMAL/실패 0/최소간격 5.17ms/생존 true → kdu 안전 확정.
Codex 빌드 거부 → mslc.c 직접 작성. C4129, 0xC0000010 반복, IoCreateDevice 회귀.
Codex 심볼 분석으로 CONNECT 0x0080·콜백 PULONG 확정, g_Attached NULL 지적 → tgt 직접 전달로 재작성.
DIAG 8바이트 실패 → Codex가 24바이트 배치 판정 → 0xC0000043(kbdhid 중복 거부). 훅 스캔 조건을 커널 코드 포인터로 바꿔 connected=1. 물리 키 b는 통과.
주입 시 재부팅 2회. 장치 포인터를 스캔값→tgt로 수정. connected=1, dev=0xFFFFC089806957C0, unit=0까지 확인. a 주입 미실행.

## 경로
firmware: mslc.c, mslc.orig.c, mslc.sys, build.ps1, NalDrv.sys
kdu: C:\mapland\kdu\kdu.exe, drv64.dll / 소스 kdu-src
stageA.ps1, stageA_cleanup.log, .venv
reader\ (stage3_reader.py, run_stage3_validation.py, _stage3_discovery\)
mapland_macro\ (live_view.py, motion.py, navigation.py, numeric_*.py, policy.py)
tools\ (probe*.py, dtest*.py, kdump*.py, stress.py)
work\stage4-actual-18344\discovery-222620-e3edc56a\actor_plan.json, work\actor_plan_fresh.json
work\plan-soak\20261111-223631\, work\stage3-validation\20261111-222206\cold-discovery\
ac\, ac_sys\
미확인: MaplelandLiveMap.pyw, live_map_config.json

## 환경
Win10 19045 x64, venv Python 3.12.10, kdu provider 39. SecureBoot·차단목록 해제, testsigning off, UF=kbdclass, 서비스 disabled. VS2022 BuildTools+WDK 19041, /p:PlatformToolset=v143. EV 인증서 없음.

## 읽기 (검증 완료)
kdu -provider 39 -map. IoCreateDriver(&name, RealEntry), \Device\mslcNN+\DosDevices\mslcNN, 빌드마다 NN 증가.
IOCTL_COPY 0x00222000 {Pid,Src,Size}: PsLookupProcessByProcessId→CopyMem. IOCTL_KMEM 0x00222008: 커널 VA.
복사는 KeStackAttachProcess→4KB 루프→MmCopyMemory(MM_COPY_MEMORY_VIRTUAL)→detach, __try/__except. MmCopyMemory는 폴트를 NTSTATUS로 돌려줘 스캔이 안 죽는다.

## 입력 (미검증)
IOCTL_INPUT 0x00222004 {Vk,Up}, Up>1 거부.
kbdclass 확장 ClassService 슬롯을 SvcForward로 교체. 물리는 SvcForward→g_Svc 전달·UnitId 학습, 주입은 g_Svc 직접 호출.
CONNECT는 kbdhid에서 0xC0000043 거부. 콜백 교체 없이는 재연결 불가.
확인값: connected=1, status=0x0, dev=0xFFFFC089806957C0, unit=0.

## 고친 결함
CONNECT 0x008→0x0080 / 콜백 4번째 PULONG / &kd+1→로컬 ULONG / g_Attached NULL 제거 / 훅 스캔 조건 / DIAG 8→32바이트 / 장치 포인터→tgt / InjectKey 스택 초과 쓰기

## DIAG 계약
24바이트: Status(0)/Pad0(4)/Returned(8)=g_ClassDev/Connected(16)/Pad1(20)=g_UnitId. 8바이트면 0xC000000D(Win32 87). 호출은 32바이트.

## 함정
붙여넣기 잘림 → 작은따옴표 배열+백틱n 또는 파일 실행. here-string은 파일에서 깨진다. admin은 S-1-16-12288로 판정. UF는 무조건 덮어쓰고 즉시 재부팅. json은 UTF8Encoding($false). 재부팅하면 Add-Type 사라짐. 빌드마다 이름 증가.

## 남은 일
1. a 주입 재시도(재부팅 시 IRQL PASSIVE 또는 워크아이템)
2. 마우스: IOCTL_POINTER, MOUSE_INPUT_DATA, MOUSE_MOVE_ABSOLUTE, 클라→스크린→정규화, DPI, 3초 해제
3. 벽면 150ms 탭 → ΔX 부호 → 게이트 배선, 10분 주행
4. 재부팅 시 콜드탐색+새 actor plan
5. FakerInput 폴백(저장소 아카이브, 배포 패키지 확인)
