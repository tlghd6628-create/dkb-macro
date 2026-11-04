두 PC의 Claude가 함께 작업하는 저장소입니다. 작업 전에 @HANDOFF.md 와 @COLLABORATION.md 를 읽고, 사용자에게는 한국어로 보고합니다.

- 시작할 때 `git pull`, `gh issue list`로 상대 PC가 맡은 일을 확인합니다.
- 맡을 이슈에 담당 PC 라벨과 건드릴 파일을 적은 뒤 시작합니다.
- 상대 세션과는 `ListAgents`와 `SendMessage`로 바로 얘기하고, 결정한 내용은 이슈에 남깁니다.
- 저장 화면·가짜 입력 검사를 실제 게임 성공으로 보고하지 않습니다.
- 채팅 답변은 .claude/skills/caveman/SKILL.md 규칙으로 짧게 씁니다. 코드·커밋·이슈·PR과 소비·보안 경고, 사용자에게 묻는 질문은 평문으로 씁니다.
