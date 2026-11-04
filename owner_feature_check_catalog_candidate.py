"""Read-only inventory for the feature-check candidate.

Names come from the installed GUI schema, current owner schedule, native
module exports and shipped template filenames.  A native ``run_*`` export is
evidence that a callable exists, NOT permission to invoke it: many entries
spend resources, claim rewards, enter combat, or change game state.

``templates`` contains filenames under profiles/DKB/templates; it is a small
set of existing evidence, not a complete list of ROIs or proof of recognition.
An empty list means not identified, not that a component is verified.
"""


def item(id,name,group,settings=(),native=(),templates=(),**extra):
    return dict(id=id,name=name,group=group,settings=list(settings),
                native=list(native),templates=list(templates),**extra)


CHECKS=[
 item('schedule','스케줄·예약 충돌','일정',schedule_only=True),
 item('main','메인퀘스트','임무',native=[('project_adapter.main_quest','run_main_quest')],templates=['버튼_전체매뉴_임무.png','체크_임무.png']),
 item('sub','서사퀘스트','임무',templates=['버튼_전체매뉴_임무.png','체크_임무.png']),
 item('daily_quest','일일 임무','임무',['auto_schedule.daily_quest.enabled'],[('project_adapter.mission_quests','run_mission_quests')],['버튼_임무_일일탭.png','체크_임무_5.png']),
 item('weekly_quest','주간 임무','임무',['auto_schedule.weekly_quest.enabled'],[('project_adapter.mission_quests','run_mission_quests')],['버튼_임무_주간탭.png','체크_임무_5.png']),
 item('folktale','전래동화 임무','임무',['auto_schedule.folktale.enabled'],[('project_adapter.folktale','run_folktale')],['버튼_임무_전래동화탭.png']),
 item('coupon','쿠폰 등록','준비',['main_quest.first_coupon.enabled'],[('project_adapter.coupon_registration','run_coupon_registration')],['버튼_전체매뉴_설정_쿠폰등록.png']),
 item('hunt','자동사냥·사냥터','준비',['common.potion_and_favorite.enabled','common.potion_and_favorite.source','common.potion_and_favorite.slot'],[('project_adapter.favorite_hunt','run_favorite_hunt')]),
 item('potion','물약 구매','준비',['common.potion_and_favorite.enabled','common.potion_and_favorite.potion_tier'],[('project_adapter.town_services','run_potion_purchase')]),
 item('inventory','인벤토리·초기 장비','준비',['auto_rewards.inventory_use.enabled'],[('project_adapter.market_inventory','run_inventory_use'),('project_adapter.market_inventory','open_inventory')],['버튼_인벤토리.png','버튼_인벤토리_희귀무기상자.png'],menu_group='inventory'),
 item('gear','장비 성장','성장',['auto_growth.equipment.enabled'],[('project_adapter.market_inventory','run_growth_equipment'),('project_adapter.achievement_rewards','run_growth_entry')],['버튼_전체매뉴_성장.png','버튼_성장_장비탭.png','체크_성장.png'],menu_group='growth'),
 item('gear_enhance','장비 강화','성장',['auto_growth.equipment.enabled'],templates=['버튼_성장_강화.png','체크_성장.png'],menu_group='growth'),
 item('gear_break','장비 돌파','성장',['auto_growth.equipment.enabled'],templates=['버튼_성장_장비_돌파.png','체크_성장.png'],menu_group='growth'),
 item('gear_awaken','장비 각성','성장',['auto_growth.equipment.enabled'],templates=['버튼_성장_장비_각성.png','체크_성장.png'],menu_group='growth'),
 item('blessing_growth','가호 성장','성장',['auto_growth.blessing.enabled'],[('project_adapter.achievement_rewards','run_growth_entry')],['버튼_성장_가호탭.png','체크_성장.png'],menu_group='growth'),
 item('skill_growth','도술 성장','성장',['auto_growth.taoist.enabled'],templates=['버튼_성장_도술탭.png','체크_성장.png'],menu_group='growth'),
 item('skill_preset','도술 프리셋','성장',['common.skill_preset.enabled','common.skill_preset.choice'],[('project_adapter.skill_preset','run_skill_preset')],['버튼_프리셋.png','체크_프리셋.png'],menu_group='skill'),
 item('energy','기운 발현','성장',['auto_growth.energy.enabled'],[('project_adapter.achievement_rewards','run_energy_entry')],['버튼_전체매뉴_기운발현.png','체크_기운발현_기운발현.png'],menu_group='energy'),
 item('inner_path','내면의 길','성장',['inner_path.enabled']),
 item('spirit','영기 수련','성장',['auto_growth.spirit_training.enabled','auto_growth.spirit_training.interval_minutes'],[('project_adapter.spirit_training','run_spirit_training')],['버튼_전체매뉴_영기수련.png','체크_영기수련.png']),
 item('blessing_reward','가호 보상','보상',['auto_rewards.blessing.enabled'],[('project_adapter.achievement_rewards','run_blessing_rewards')],['버튼_전체매뉴_가호.png','체크_전체매뉴_가호.png']),
 item('seal_release','단 봉인 해제','보상',['auto_rewards.seal_release.enabled'],[('project_adapter.seal_release','run_seal_release')],['버튼_전체매뉴_단봉인해제.png','체크_단봉인해제.png']),
 item('guide','길라잡이','보상',['auto_rewards.guide.enabled'],[('project_adapter.guide_rewards','run_guide_rewards')],['버튼_길라잡이.png','체크_길라잡이.png']),
 item('events','이벤트·출석','보상',['auto_rewards.event.enabled'],[('project_adapter.event_rewards','run_event_rewards')],['버튼_이벤트.png','체크_이벤트.png']),
 item('mail','우편','보상',['auto_rewards.mail.enabled'],[('project_adapter.mail_rewards','run_mail_rewards')],['버튼_우편.png','체크_우편함.png']),
 item('achievement','업적','보상',['auto_rewards.achievement.enabled'],[('project_adapter.achievement_rewards','run_achievement_rewards')],['버튼_전체매뉴_업적.png','버튼_업적_받기.png']),
 item('album','화첩','보상',['auto_rewards.album.enabled'],[('project_adapter.achievement_rewards','run_album_rewards')],['체크_전체매뉴_화첩.png','버튼_전체매뉴_화첩_완성.png']),
 item('training_log','도사 수행록','보상',['auto_rewards.training_log.enabled']),
 item('daily_dungeon','일일 비경','비경',['auto_challenge.secret_exploration.enabled','auto_challenge.secret_exploration.type'],[('project_adapter.secret_exploration','run_secret_exploration')],['버튼_전체매뉴_비경.png','체크_비경.png','체크_비경_단계선택.png'],menu_group='dungeon'),
 item('daily24_dungeon','일일 24시간 비경','비경',['auto_challenge.secret_exploration_always.enabled','auto_challenge.secret_exploration_always.stage','auto_challenge.secret_exploration_always.hours','auto_challenge.secret_exploration_always.type'],[('project_adapter.secret_exploration','run_secret_exploration')],['버튼_전체매뉴_비경.png','체크_비경.png','체크_비경_상시고독마을.png'],menu_group='dungeon'),
 item('weekly_dungeon','전래동화 비경 5시간','비경',['auto_challenge.secret_folktale_5h.enabled','auto_challenge.secret_folktale_5h.target'],[('project_adapter.secret_folktale','run_folktale_exploration')],['버튼_전체매뉴_비경.png','버튼_비경_전래동화탭.png'],menu_group='dungeon'),
 item('weekly24_dungeon','전래동화 비경 24시간','비경',['auto_challenge.secret_folktale.enabled','auto_challenge.secret_folktale.stage','auto_challenge.secret_folktale.hours','auto_challenge.secret_folktale.target'],[('project_adapter.secret_folktale','run_folktale_exploration')],['버튼_전체매뉴_비경.png','버튼_비경_전래동화탭.png'],menu_group='dungeon'),
 item('mangwi','만귀비경','비경'),
 item('tower','승천의 탑','도전',['auto_challenge.ascension_tower.enabled'],[('project_adapter.ascension_tower','run_ascension_tower')],['버튼_전체매뉴_승천.png','버튼_승천_다음단계.png']),
 item('treasure','보물찾기','도전',['auto_challenge.treasure_hunt.enabled','auto_challenge.treasure_hunt.region'],[('project_adapter.treasure_entry','run_treasure_region_entry')],['버튼_보물찾기.png','체크_보물찾기.png']),
 item('clan_training','문파 협력수련','문파',['auto_growth.clan_cooperative_training.enabled','auto_growth.clan_cooperative_training.lamp'],[('project_adapter.clan_cooperative_training','run_clan_cooperative_training')],['버튼_전체매뉴_문파.png','체크_문파.png']),
 item('clan_request','문파 보스 신청','문파',['auto_schedule.clan_boss_request.enabled'],[('project_adapter.clan_boss_request','run_clan_boss_request')],['버튼_문파_전투.png','버튼_문파_요신토벌령.png','버튼_문파_결계지방어.png']),
 item('clan_artifact','신기 쟁탈전','문파',['auto_schedule.artifact_charm.enabled'],[('project_adapter.clan_boss_request','run_clan_boss_request')],['버튼_문파_신기쟁탈전.png','체크_문파_신기쟁탈전.png']),
 item('clan_garden','미혹의 정원','문파',['auto_schedule.artifact_charm.enabled'],[('project_adapter.clan_boss_request','run_clan_boss_request')],['버튼_문파_미혹의정원.png','체크_문파_미혹의정원.png']),
 item('field_boss','월드보스','보스',['auto_schedule.field_boss.enabled'],[('project_adapter.field_boss','run_field_boss_entry')],['버튼_보스.png','버튼_보스_필드보스탭.png']),
 item('raid','보스 레이드','보스',['auto_schedule.boss_raid.enabled','auto_schedule.boss_raid.stage','auto_schedule.boss_raid.reward_ticket'],[('project_adapter.boss_raid','run_boss_raid')],['버튼_보스.png','버튼_보스_레이드탭.png']),
 item('falling','낙화의 전장','보스',['auto_schedule.falling_battle.enabled'],[('project_adapter.falling_battle','run_falling_battle')],['버튼_전체매뉴_낙화.png','체크_낙화_입장완료.png']),
 item('market','거래소 등록','기타',['auto_register.market.enabled'],[('project_adapter.market_inventory','run_market_inventory')],['버튼_거래소.png','체크_거래소.png']),
 item('disassembly','장비 분해','기타',['auto_register.equipment_disassembly.enabled'],[('project_adapter.market_inventory','run_equipment_disassembly')],['버튼_인벤토리_분해.png','버튼_인벤토리_분해실행.png']),
 item('daily_restart','스케줄 재시작','기타',['common.daily_restart.enabled','common.daily_restart.hour','common.daily_restart.minute']),
 item('shop','잡화상점 구매','구매',native=[('owner_shop_runtime_candidate','dispatch_configured')]),
 item('box_choice','상자 선택·분배','구매',['auto_rewards.inventory_use.enabled'],[('owner_starter_choice_candidate','install'),('owner_coupon_skills_candidate','process'),('owner_energy_next_integration_candidate','attempt')]),
 item('gear_swap','장비 교체','성장',['auto_rewards.inventory_use.enabled'],[('owner_equip_runtime_install_candidate','install')]),
 item('skill_learn','도술 학습','성장',native=[('owner_skill_goal','install')]),
 item('work_resume','원래 작업 복귀','공통',native=[('owner_work_resume','install')]),
 item('reconnect','접속 끊김 복구','공통',native=[('owner_reconnect','install')]),
 item('user_controls','시작·일시정지·중지','공통',native=[('owner_controls','install')]),
 item('telegram','텔레그램 제어·조회','공통',native=[('owner_telegram_ui','TelegramPanel')]),
 item('auto_update','자동 업데이트','공통',native=[('owner_auto_update','install')]),
 item('daily_shop','일일 교환 상점','구매',native=[('owner_shop_runtime_candidate','dispatch_configured')]),
 item('weekly_shop','주간 교환 상점','구매',native=[('owner_shop_runtime_candidate','dispatch_configured')]),
 item('offline','오프라인 사냥 준비','수동'),
 item('falling_elite','낙화 암영 무도가','수동'),
 item('season','시즌·기간한정 보상','수동'),
]

# Inspection metadata only.  None is invoked by importing this module.
# Even an 'open' helper changes UI state and must be called only by the sole
# input owner with explicit stop/restart/context guards and verified cleanup.
MENU_HELPERS=[
 {'menu_group':'inventory','callable':'project_adapter.market_inventory.open_inventory',
  'signature':'(service, *, click_button=None, timeout=10)',
  'scope':'인벤토리 열기; 기존 래퍼가 캐릭터·장착 관찰 기록을 할 수 있음', 'verified_read_only':False},
 {'menu_group':'growth','callable':'project_adapter.achievement_rewards.run_growth_entry',
  'signature':'(adapter, context, inputs, *, return_to_loop=False, equipment_test=False, blessing_test=False)',
  'scope':'이름·인자만 확인; 인자별 내부 입력/자원 소비 미확인', 'verified_read_only':False},
 {'menu_group':'energy','callable':'project_adapter.achievement_rewards.run_energy_entry',
  'signature':'(adapter, context, inputs, *, process=False)',
  'scope':'process=False 내부 동작 미확인; 안전한 메뉴 전용 호출로 가정 금지', 'verified_read_only':False},
 {'menu_group':'skill','callable':'owner_skill_ui.SkillUI.open_skills',
  'signature':'(self)', 'scope':'기존 가드 후 K키로 도술창 열기', 'verified_read_only':False},
]
