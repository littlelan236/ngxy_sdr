# 端序配置
# 由示例代码，CRC16是小端序，不再用全局变量
# big或little
ENDIAN = "little" # 串口协议帧中cmd_id和data_length的端序
ENDIAN_DATA = "big" # 串口协议中data的端序
ENDIAN_OTA = "big" # 空口帧的端序
# 港科开源中，ENDIAN="little" ENDIAN_DATA="big" 非常神秘

# 定义指令格式
SOF = 0xA5
ACCESS_CODE_SIGNAL = 0x2F6F4C74B914492E
ACCESS_CODE_JAMMING = 0x16E8D377151C712D
LEN_OTA_PAYLOAD = 0x000F

# 数据帧各结构长度（字节数）
LEN_SOF = 1
LEN_DATA_LENGTH = 2
LEN_SEQ = 1
LEN_CMD_ID = 2

LEN_ACCESS = 8
LEN_OTA_LENGTH = 2

# 空口帧access的自相关值
ACCESS_CORR_SIGNAL = 32
ACCESS_CORR_JAMMING = 32

CMD_OPTIONS = {
    # name: (cmd_id, data_length)
    "enemy_pos": (0x0A01, 24),
    "enemy_hp": (0x0A02, 12),
    "enemy_ammo": (0x0A03, 10),
    "buff_state": (0x0A04, 8),
    "gains": (0x0A05, 36),
    "jamming": (0x0A06, 6),
}

# 定义payload格式
SERIAL_FIELDS = {
    "enemy_pos": [
        ("hero_x", 2),
        ("hero_y", 2),
        ("engineer_x", 2),
        ("engineer_y", 2),
        ("infantry_3_x", 2),
        ("infantry_3_y", 2),
        ("infantry_4_x", 2),
        ("infantry_4_y", 2),
        ("aerial_x", 2),
        ("aerial_y", 2),
        ("sentry_x", 2),
        ("sentry_y", 2),
    ],
    "enemy_hp": [
        ("hero_hp", 2),
        ("engineer_hp", 2),
        ("infantry_3_hp", 2),
        ("infantry_4_hp", 2),
        ("reserved", 2),
        ("sentry_hp", 2),
    ],
    "enemy_ammo": [
        ("hero_ammo", 2),
        ("infantry_3_ammo", 2),
        ("infantry_4_ammo", 2),
        ("aerial_ammo", 2),
        ("sentry_ammo", 2),
    ],
    "buff_state": [
        ("remaining_gold", 2),
        ("total_gold", 2),
        ("macro_bits", 4), # 各种占领状态不再细分条目
    ],
    "gains": [
        ("hero_health_regen", 1),
        ("hero_cooling_boost", 2),
        ("hero_defense_boost", 1),
        ("hero_defense_debuff", 1),
        ("hero_attack_boost", 2),
        ("engineer_health_regen", 1),
        ("engineer_cooling_boost", 2),
        ("engineer_defense_boost", 1),
        ("engineer_defense_debuff", 1),
        ("engineer_attack_boost", 2),
        ("infantry_3_health_regen", 1),
        ("infantry_3_cooling_boost", 2),
        ("infantry_3_defense_boost", 1),
        ("infantry_3_defense_debuff", 1),
        ("infantry_3_attack_boost", 2),
        ("infantry_4_health_regen", 1),
        ("infantry_4_cooling_boost", 2),
        ("infantry_4_defense_boost", 1),
        ("infantry_4_defense_debuff", 1),
        ("infantry_4_attack_boost", 2),
        ("sentry_health_regen", 1),
        ("sentry_cooling_boost", 2),
        ("sentry_defense_boost", 1),
        ("sentry_defense_debuff", 1),
        ("sentry_attack_boost", 2),
        ("sentry_posture", 1),
    ],
    "jamming": [
        ("key", 6),
    ],
}
