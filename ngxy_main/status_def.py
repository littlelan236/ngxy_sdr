from dataclasses import dataclass, field
from enum import Enum


class BaseStatus:
    pass


@dataclass
class RobotStatus(BaseStatus):
    robot_id: int
    is_gimbal_power_on: bool


@dataclass
class GameStatus(BaseStatus):
    class GameStage(Enum):
        UNKNOWN = -1
        NOT_STARTED = 0
        PREPARING = 1
        REFEREE_SELF_CHECKING = 2
        FIVE_SEC_COUNTDOWN = 3
        IN_PROGRESS = 4
        IN_SETTLEMENT = 5

    current_stage: GameStage
    remaining_sec: int


@dataclass
class RadarMarkStatus(BaseStatus):
    enemy_hero: bool
    enemy_engineer: bool
    enemy_infantry_3: bool
    enemy_infantry_4: bool
    enemy_sentry: bool
    enemy_air: bool

    ally_hero: bool
    ally_engineer: bool
    ally_infantry_3: bool
    ally_infantry_4: bool
    ally_sentry: bool
    ally_air: bool


@dataclass
class RadarInfoStatus(BaseStatus):
    double_vulnerability_opportunities: int
    is_double_vulnerability_active: bool
    can_modify_password: bool


@dataclass
class PositionStatus(BaseStatus):
    @dataclass
    class Position:
        x_in_cm: int
        y_in_cm: int
        conf: float = -1.0

        def __iter__(self):
            return iter((self.x_in_cm, self.y_in_cm))

    @dataclass(frozen=True)
    class NoPosition:
        x_in_cm: int = 0
        y_in_cm: int = 0
        conf: float = -1.0

        def __iter__(self):
            return iter((self.x_in_cm, self.y_in_cm))

    class Source(Enum):
        UNKNOWN = "Unknown"
        RADAR = "Radar"
        WIRELESS = "Wireless"
        SENTRY = "Sentry"
        MIXED = "Mixed"

    _PostionOrNoPosition = Position | NoPosition

    opponent_hero: _PostionOrNoPosition = field(default_factory=NoPosition)
    opponent_engineer: _PostionOrNoPosition = field(default_factory=NoPosition)
    opponent_infantry_3: _PostionOrNoPosition = field(default_factory=NoPosition)
    opponent_infantry_4: _PostionOrNoPosition = field(default_factory=NoPosition)
    opponent_sentry: _PostionOrNoPosition = field(default_factory=NoPosition)
    opponent_aerial: _PostionOrNoPosition = field(default_factory=NoPosition)

    ally_hero: _PostionOrNoPosition = field(default_factory=NoPosition)
    ally_engineer: _PostionOrNoPosition = field(default_factory=NoPosition)
    ally_infantry_3: _PostionOrNoPosition = field(default_factory=NoPosition)
    ally_infantry_4: _PostionOrNoPosition = field(default_factory=NoPosition)
    ally_sentry: _PostionOrNoPosition = field(default_factory=NoPosition)
    ally_aerial: NoPosition = field(default_factory=NoPosition)  # we dont care

    source: Source = Source.UNKNOWN


# wireless specific


@dataclass
class EnemyPasswordStatus(BaseStatus):
    password: str


# 串口协议中机器人血量信息没说数据类型
@dataclass
class EnemyHealthStatus(BaseStatus):
    enemy_hero: int
    enemy_infantry_3: int
    enemy_infantry_4: int
    enemy_sentry: int


@dataclass
class EnemyBulletStatus(BaseStatus):
    enemy_hero: int
    enemy_infantry_3: int
    enemy_infantry_4: int
    enemy_sentry: int
    enemy_air: int


@dataclass
class EnemyBuffStatus(BaseStatus):
    @dataclass
    class Buff:
        recovery_buff: int = -1
        cooling_buff: int = -1
        defence_buff: int = -1
        vulnerability_buff: int = -1
        attack_buff: int = -1

    enemy_hero: Buff
    enemy_engineer: Buff
    enemy_infantry_3: Buff
    enemy_infantry_4: Buff
    enemy_sentry: Buff


@dataclass
class EnemyTeamStatus(BaseStatus):
    @dataclass
    class RFIDStatus:
        # 除了经济信息外的其他信息用bytes传 一共四个byte
        raw_data: bytes

    enemy_coin_remaining: int
    enemy_coin_total: int
    rfid_status: RFIDStatus


# 『raw』data for forwarding only
@dataclass
class SerialRawData(BaseStatus):
    raw_data: bytes


# EnemyBulletRaw = SerialRawData
# EnemyBuffRaw = SerialRawData
EnemyTeamRaw = SerialRawData


# Uesless for now
# @dataclass
# class AllyRobotHpStatus: ...


# @dataclass
# class FieldEventStatus: ...


# @dataclass
# class DartStatus: ...

def dict_to_dataclass(data_dict)-> BaseStatus | None:
    """将字典转换为对应的dataclass实例"""
    if "hero_x" in data_dict:
        return PositionStatus(
            opponent_hero=PositionStatus.Position(data_dict["hero_x"], data_dict["hero_y"], conf=99),
            opponent_engineer=PositionStatus.Position(data_dict["engineer_x"], data_dict["engineer_y"], conf=99),
            opponent_infantry_3=PositionStatus.Position(data_dict["infantry_3_x"], data_dict["infantry_3_y"], conf=99),
            opponent_infantry_4=PositionStatus.Position(data_dict["infantry_4_x"], data_dict["infantry_4_y"], conf=99),
            opponent_sentry=PositionStatus.Position(data_dict["sentry_x"], data_dict["sentry_y"], conf=99),
            opponent_aerial=PositionStatus.Position(data_dict["aerial_x"], data_dict["aerial_y"], conf=99),
            ally_hero=PositionStatus.NoPosition, # 友军位置不在雷达解析信息范围内
            ally_engineer=PositionStatus.NoPosition,
            ally_infantry_3=PositionStatus.NoPosition,
            ally_infantry_4=PositionStatus.NoPosition,
            ally_sentry=PositionStatus.NoPosition,
            ally_aerial=PositionStatus.NoPosition,
            source=PositionStatus.Source.RADAR
        )
    elif "hero_hp" in data_dict:
        return EnemyHealthStatus(
            enemy_hero=data_dict["hero_hp"],
            enemy_infantry_3=data_dict["infantry_3_hp"],
            enemy_infantry_4=data_dict["infantry_4_hp"],
            enemy_sentry=data_dict["sentry_hp"],
        )
    elif "hero_ammo" in data_dict:
        return EnemyBulletStatus(
            enemy_hero=data_dict["hero_ammo"],
            enemy_infantry_3=data_dict["infantry_3_ammo"],
            enemy_infantry_4=data_dict["infantry_4_ammo"],
            enemy_sentry=data_dict["sentry_ammo"],
            enemy_air=data_dict["aerial_ammo"],
        )
    elif "remaining_gold" in data_dict:
        return EnemyTeamStatus(
            enemy_coin_remaining=data_dict["remaining_gold"],
            enemy_coin_total=data_dict["total_gold"],
            rfid_status=EnemyTeamStatus.RFIDStatus(raw_data=data_dict["rfid_data"])
        )

    elif "hero_health_regen" in data_dict:
        return EnemyBuffStatus(
            enemy_hero=EnemyBuffStatus.Buff(
                recovery_buff=data_dict["hero_health_regen"],
                cooling_buff=data_dict["hero_cooling_boost"],
                defence_buff=data_dict["hero_defense_boost"],
                vulnerability_buff=data_dict["hero_defense_debuff"],
                attack_buff=data_dict["hero_attack_boost"],
            ),
            enemy_engineer=EnemyBuffStatus.Buff(
                recovery_buff=data_dict["engineer_health_regen"],
                cooling_buff=data_dict["engineer_cooling_boost"],
                defence_buff=data_dict["engineer_defense_boost"],
                vulnerability_buff=data_dict["engineer_defense_debuff"],
                attack_buff=data_dict["engineer_attack_boost"],
            ),
            enemy_infantry_3=EnemyBuffStatus.Buff(
                recovery_buff=data_dict["infantry_3_health_regen"],
                cooling_buff=data_dict["infantry_3_cooling_boost"],
                defence_buff=data_dict["infantry_3_defense_boost"],
                vulnerability_buff=data_dict["infantry_3_defense_debuff"],
                attack_buff=data_dict["infantry_3_attack_boost"],
            ),
            enemy_infantry_4=EnemyBuffStatus.Buff(
                recovery_buff=data_dict["infantry_4_health_regen"],
                cooling_buff=data_dict["infantry_4_cooling_boost"],
                defence_buff=data_dict["infantry_4_defense_boost"],
                vulnerability_buff=data_dict["infantry_4_defense_debuff"],
                attack_buff=data_dict["infantry_4_attack_boost"],
            ),
            enemy_sentry=EnemyBuffStatus.Buff(
                recovery_buff=data_dict["sentry_health_regen"],
                cooling_buff=data_dict["sentry_cooling_boost"],
                defence_buff=data_dict["sentry_defense_boost"],
                vulnerability_buff=data_dict["sentry_defense_debuff"],
                attack_buff=data_dict["sentry_attack_boost"],
            )
        )
    elif "key" in data_dict:
        return EnemyPasswordStatus(password=data_dict["key"])
    else:
        return None