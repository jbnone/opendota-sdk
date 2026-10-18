"""Hero-related enumerations exposed on `Hero` and `HeroStats` models, and hero names for lookups."""

from enum import IntEnum, StrEnum


class HeroSkillBracket(IntEnum):
    """Dota 2 rank medal tiers, used by OpenDota to bucket pick/win statistics.

    Values match the numeric prefixes of the `/heroStats` bracket keys (`1_pick`,
    `1_win`, ...). `IMMORTAL` is always reported as zero picks and wins, since OpenDota
    withholds that bracket from the public API.
    """

    HERALD = 1
    GUARDIAN = 2
    CRUSADER = 3
    ARCHON = 4
    LEGEND = 5
    ANCIENT = 6
    DIVINE = 7
    # OpenDota reports zeroes here; Immortal bracket data is withheld from the public API.
    IMMORTAL = 8


class HeroRole(StrEnum):
    """A hero's suggested in-game role(s), as classified by dotaconstants."""

    CARRY = "Carry"
    SUPPORT = "Support"
    NUKER = "Nuker"
    DISABLER = "Disabler"
    JUNGLER = "Jungler"
    DURABLE = "Durable"
    ESCAPE = "Escape"
    PUSHER = "Pusher"


class HeroAttackType(StrEnum):
    """Whether a hero attacks at melee or ranged distance."""

    MELEE = "Melee"
    RANGED = "Ranged"


class HeroPrimaryAttribute(StrEnum):
    """A hero's primary stat, which scales their damage output.

    `ALL` denotes universal heroes, whose damage scales with every attribute.
    """

    STRENGTH = "str"
    AGILITY = "agi"
    INTELLIGENCE = "int"
    ALL = "all"


class BenchmarkMetric(StrEnum):
    """A per-hero statistic that `/benchmarks` reports percentile curves for.

    Members are named in full (`GOLD_PER_MINUTE`), while values are the keys OpenDota
    uses (`"gold_per_min"`), so a member equals and hashes as its key, as `HeroName`
    does. Pass a member to `HeroBenchmarks.get()`. The members mirror the keys of the
    recorded payload; a metric OpenDota adds later is still reachable by its plain key
    as a string until this enum gains a member for it.
    """

    GOLD_PER_MINUTE = "gold_per_min"
    EXPERIENCE_PER_MINUTE = "xp_per_min"
    KILLS_PER_MINUTE = "kills_per_min"
    DEATHS_PER_MINUTE = "deaths_per_min"
    ASSISTS_PER_MINUTE = "assists_per_min"
    LAST_HITS_PER_MINUTE = "last_hits_per_min"
    DENIES_PER_MINUTE = "denies_per_min"
    HERO_DAMAGE_PER_MINUTE = "hero_damage_per_min"
    HERO_HEALING_PER_MINUTE = "hero_healing_per_min"
    TOWER_DAMAGE = "tower_damage"


class HeroName(StrEnum):
    """Every hero's internal name, so lookups don't need the raw `npc_dota_hero_*` string.

    Members are named after the hero's in-game name, while values are the internal names
    OpenDota uses, which often differ: `ZEUS` is `"npc_dota_hero_zuus"` and
    `NATURES_PROPHET` is `"npc_dota_hero_furion"`. Pass a member wherever a hero name is
    accepted, as in `await client.get_hero(HeroName.ANTI_MAGE)`.

    Each member is a `str` equal to its value, so it compares equal to `Hero.name` and works
    anywhere a plain internal name does. The members mirror the vendored dotaconstants
    fixture. A hero added in a later patch can still be looked up by its internal name as
    a plain string until this enum gains a member for it.
    """

    ABADDON = "npc_dota_hero_abaddon"
    ALCHEMIST = "npc_dota_hero_alchemist"
    ANCIENT_APPARITION = "npc_dota_hero_ancient_apparition"
    ANTI_MAGE = "npc_dota_hero_antimage"
    ARC_WARDEN = "npc_dota_hero_arc_warden"
    AXE = "npc_dota_hero_axe"
    BANE = "npc_dota_hero_bane"
    BATRIDER = "npc_dota_hero_batrider"
    BEASTMASTER = "npc_dota_hero_beastmaster"
    BLOODSEEKER = "npc_dota_hero_bloodseeker"
    BOUNTY_HUNTER = "npc_dota_hero_bounty_hunter"
    BREWMASTER = "npc_dota_hero_brewmaster"
    BRISTLEBACK = "npc_dota_hero_bristleback"
    BROODMOTHER = "npc_dota_hero_broodmother"
    CENTAUR_WARRUNNER = "npc_dota_hero_centaur"
    CHAOS_KNIGHT = "npc_dota_hero_chaos_knight"
    CHEN = "npc_dota_hero_chen"
    CLINKZ = "npc_dota_hero_clinkz"
    CLOCKWERK = "npc_dota_hero_rattletrap"
    CRYSTAL_MAIDEN = "npc_dota_hero_crystal_maiden"
    DARK_SEER = "npc_dota_hero_dark_seer"
    DARK_WILLOW = "npc_dota_hero_dark_willow"
    DAWNBREAKER = "npc_dota_hero_dawnbreaker"
    DAZZLE = "npc_dota_hero_dazzle"
    DEATH_PROPHET = "npc_dota_hero_death_prophet"
    DISRUPTOR = "npc_dota_hero_disruptor"
    DOOM = "npc_dota_hero_doom_bringer"
    DRAGON_KNIGHT = "npc_dota_hero_dragon_knight"
    DROW_RANGER = "npc_dota_hero_drow_ranger"
    EARTHSHAKER = "npc_dota_hero_earthshaker"
    EARTH_SPIRIT = "npc_dota_hero_earth_spirit"
    ELDER_TITAN = "npc_dota_hero_elder_titan"
    EMBER_SPIRIT = "npc_dota_hero_ember_spirit"
    ENCHANTRESS = "npc_dota_hero_enchantress"
    ENIGMA = "npc_dota_hero_enigma"
    FACELESS_VOID = "npc_dota_hero_faceless_void"
    GRIMSTROKE = "npc_dota_hero_grimstroke"
    GYROCOPTER = "npc_dota_hero_gyrocopter"
    HOODWINK = "npc_dota_hero_hoodwink"
    HUSKAR = "npc_dota_hero_huskar"
    INVOKER = "npc_dota_hero_invoker"
    IO = "npc_dota_hero_wisp"
    JAKIRO = "npc_dota_hero_jakiro"
    JUGGERNAUT = "npc_dota_hero_juggernaut"
    KEEPER_OF_THE_LIGHT = "npc_dota_hero_keeper_of_the_light"
    KEZ = "npc_dota_hero_kez"
    KUNKKA = "npc_dota_hero_kunkka"
    LARGO = "npc_dota_hero_largo"
    LEGION_COMMANDER = "npc_dota_hero_legion_commander"
    LESHRAC = "npc_dota_hero_leshrac"
    LICH = "npc_dota_hero_lich"
    LIFESTEALER = "npc_dota_hero_life_stealer"
    LINA = "npc_dota_hero_lina"
    LION = "npc_dota_hero_lion"
    LONE_DRUID = "npc_dota_hero_lone_druid"
    LUNA = "npc_dota_hero_luna"
    LYCAN = "npc_dota_hero_lycan"
    MAGNUS = "npc_dota_hero_magnataur"
    MARCI = "npc_dota_hero_marci"
    MARS = "npc_dota_hero_mars"
    MEDUSA = "npc_dota_hero_medusa"
    MEEPO = "npc_dota_hero_meepo"
    MIRANA = "npc_dota_hero_mirana"
    MONKEY_KING = "npc_dota_hero_monkey_king"
    MORPHLING = "npc_dota_hero_morphling"
    MUERTA = "npc_dota_hero_muerta"
    NAGA_SIREN = "npc_dota_hero_naga_siren"
    NATURES_PROPHET = "npc_dota_hero_furion"
    NECROPHOS = "npc_dota_hero_necrolyte"
    NIGHT_STALKER = "npc_dota_hero_night_stalker"
    NYX_ASSASSIN = "npc_dota_hero_nyx_assassin"
    OGRE_MAGI = "npc_dota_hero_ogre_magi"
    OMNIKNIGHT = "npc_dota_hero_omniknight"
    ORACLE = "npc_dota_hero_oracle"
    OUTWORLD_DEVOURER = "npc_dota_hero_obsidian_destroyer"
    PANGOLIER = "npc_dota_hero_pangolier"
    PHANTOM_ASSASSIN = "npc_dota_hero_phantom_assassin"
    PHANTOM_LANCER = "npc_dota_hero_phantom_lancer"
    PHOENIX = "npc_dota_hero_phoenix"
    PRIMAL_BEAST = "npc_dota_hero_primal_beast"
    PUCK = "npc_dota_hero_puck"
    PUDGE = "npc_dota_hero_pudge"
    PUGNA = "npc_dota_hero_pugna"
    QUEEN_OF_PAIN = "npc_dota_hero_queenofpain"
    RAZOR = "npc_dota_hero_razor"
    RIKI = "npc_dota_hero_riki"
    RING_MASTER = "npc_dota_hero_ringmaster"
    RUBICK = "npc_dota_hero_rubick"
    SAND_KING = "npc_dota_hero_sand_king"
    SHADOW_DEMON = "npc_dota_hero_shadow_demon"
    SHADOW_FIEND = "npc_dota_hero_nevermore"
    SHADOW_SHAMAN = "npc_dota_hero_shadow_shaman"
    SILENCER = "npc_dota_hero_silencer"
    SKYWRATH_MAGE = "npc_dota_hero_skywrath_mage"
    SLARDAR = "npc_dota_hero_slardar"
    SLARK = "npc_dota_hero_slark"
    SNAPFIRE = "npc_dota_hero_snapfire"
    SNIPER = "npc_dota_hero_sniper"
    SPECTRE = "npc_dota_hero_spectre"
    SPIRIT_BREAKER = "npc_dota_hero_spirit_breaker"
    STORM_SPIRIT = "npc_dota_hero_storm_spirit"
    SVEN = "npc_dota_hero_sven"
    TECHIES = "npc_dota_hero_techies"
    TEMPLAR_ASSASSIN = "npc_dota_hero_templar_assassin"
    TERRORBLADE = "npc_dota_hero_terrorblade"
    TIDEHUNTER = "npc_dota_hero_tidehunter"
    TIMBERSAW = "npc_dota_hero_shredder"
    TINKER = "npc_dota_hero_tinker"
    TINY = "npc_dota_hero_tiny"
    TREANT_PROTECTOR = "npc_dota_hero_treant"
    TROLL_WARLORD = "npc_dota_hero_troll_warlord"
    TUSK = "npc_dota_hero_tusk"
    UNDERLORD = "npc_dota_hero_abyssal_underlord"
    UNDYING = "npc_dota_hero_undying"
    URSA = "npc_dota_hero_ursa"
    VENGEFUL_SPIRIT = "npc_dota_hero_vengefulspirit"
    VENOMANCER = "npc_dota_hero_venomancer"
    VIPER = "npc_dota_hero_viper"
    VISAGE = "npc_dota_hero_visage"
    VOID_SPIRIT = "npc_dota_hero_void_spirit"
    WARLOCK = "npc_dota_hero_warlock"
    WEAVER = "npc_dota_hero_weaver"
    WINDRANGER = "npc_dota_hero_windrunner"
    WINTER_WYVERN = "npc_dota_hero_winter_wyvern"
    WITCH_DOCTOR = "npc_dota_hero_witch_doctor"
    WRAITH_KING = "npc_dota_hero_skeleton_king"
    ZEUS = "npc_dota_hero_zuus"
