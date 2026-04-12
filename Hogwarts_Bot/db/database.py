import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def initialize(self) -> None:
        schema_path = Path(__file__).with_name("schema.sql")
        schema_sql = schema_path.read_text(encoding="utf-8")

        with self.connect() as conn:
            conn.executescript(schema_sql)
            self._run_migrations(conn)
            self._ensure_indexes(conn)
            conn.commit()

    def _run_migrations(self, conn: sqlite3.Connection) -> None:
        user_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }

        if "bio" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN bio TEXT NULL")

        if "birth_day" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN birth_day INTEGER NULL")

        if "birth_month" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN birth_month INTEGER NULL")

        if "xp" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN xp INTEGER NOT NULL DEFAULT 0")

        if "level" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN level INTEGER NOT NULL DEFAULT 1")

        if "last_xp_at" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN last_xp_at TEXT NULL")

        if "year_start_at" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN year_start_at TEXT NULL")

        if "last_year_message_at" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN last_year_message_at TEXT NULL")

        if "year_initialized_at" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN year_initialized_at TEXT NULL")

        existing_tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        if "guild_role_mappings" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS guild_role_mappings (
                    guild_id INTEGER NOT NULL,
                    role_key TEXT NOT NULL,
                    role_id INTEGER NOT NULL,
                    role_name TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, role_key)
                )
                """
            )

        if "user_chocolate_frog_cards" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_chocolate_frog_cards (
                    user_id INTEGER NOT NULL,
                    card_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    first_discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, card_id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
                """
            )

        if "casual_quiz_channels" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS casual_quiz_channels (
                    channel_id INTEGER PRIMARY KEY,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    current_question_id INTEGER NULL,
                    last_asked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        if "quiz_question_history" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quiz_question_history (
                    channel_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    asked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (channel_id, question_id),
                    FOREIGN KEY (channel_id) REFERENCES casual_quiz_channels(channel_id) ON DELETE CASCADE
                )
                """
            )

        if "birthday_announcements" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS birthday_announcements (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    birthday_user_id INTEGER NOT NULL,
                    announcement_date TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        if "birthday_gift_claims" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS birthday_gift_claims (
                    message_id INTEGER NOT NULL,
                    giver_user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (message_id, giver_user_id),
                    FOREIGN KEY (message_id) REFERENCES birthday_announcements(message_id) ON DELETE CASCADE
                )
                """
            )

        if "media_channels" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS media_channels (
                    channel_id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        if "media_posts" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS media_posts (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    author_user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    closes_at TEXT NOT NULL,
                    is_closed INTEGER NOT NULL DEFAULT 0,
                    reward_points_per_vote INTEGER NOT NULL DEFAULT 3,
                    rewarded_points INTEGER NOT NULL DEFAULT 0
                )
                """
            )

        if "media_votes" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS media_votes (
                    message_id INTEGER NOT NULL,
                    voter_user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (message_id, voter_user_id),
                    FOREIGN KEY (message_id) REFERENCES media_posts(message_id) ON DELETE CASCADE
                )
                """
            )

        if "reaction_role_channels" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reaction_role_channels (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        if "reaction_role_messages" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reaction_role_messages (
                    guild_id INTEGER NOT NULL,
                    group_key TEXT NOT NULL,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, group_key)
                )
                """
            )

        if "reaction_role_memberships" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reaction_role_memberships (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    group_key TEXT NOT NULL,
                    role_key TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, user_id, group_key, role_key)
                )
                """
            )

        if "quidditch_position_progress" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quidditch_position_progress (
                    user_id INTEGER NOT NULL,
                    position_key TEXT NOT NULL,
                    level INTEGER NOT NULL DEFAULT 1,
                    xp INTEGER NOT NULL DEFAULT 0,
                    last_xp_at TEXT NULL,
                    daily_xp INTEGER NOT NULL DEFAULT 0,
                    daily_reset_on TEXT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, position_key)
                )
                """
            )

        if "quidditch_config" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quidditch_config (
                    guild_id INTEGER PRIMARY KEY,
                    match_channel_id INTEGER NULL,
                    scoreboard_channel_id INTEGER NULL,
                    scoreboard_message_id INTEGER NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        if "quidditch_loop_control" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quidditch_loop_control (
                    guild_id INTEGER PRIMARY KEY,
                    is_enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        if "quidditch_seasons" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quidditch_seasons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    season_key TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    is_reduced INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'scheduled',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, season_key)
                )
                """
            )

        if "quidditch_fixtures" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quidditch_fixtures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    season_id INTEGER NOT NULL,
                    match_day INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    starts_at TEXT NOT NULL,
                    home_house TEXT NOT NULL,
                    away_house TEXT NOT NULL,
                    home_score INTEGER NOT NULL DEFAULT 0,
                    away_score INTEGER NOT NULL DEFAULT 0,
                    winner_house TEXT NULL,
                    status TEXT NOT NULL DEFAULT 'scheduled',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (season_id) REFERENCES quidditch_seasons(id) ON DELETE CASCADE
                )
                """
            )

        if "quidditch_house_standings" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quidditch_house_standings (
                    season_id INTEGER NOT NULL,
                    house_name TEXT NOT NULL,
                    points_scored INTEGER NOT NULL DEFAULT 0,
                    points_conceded INTEGER NOT NULL DEFAULT 0,
                    matches_played INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (season_id, house_name),
                    FOREIGN KEY (season_id) REFERENCES quidditch_seasons(id) ON DELETE CASCADE
                )
                """
            )

        if "quidditch_live_match_state" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quidditch_live_match_state (
                    fixture_id INTEGER PRIMARY KEY,
                    message_id INTEGER NULL,
                    channel_id INTEGER NULL,
                    image_path TEXT NULL,
                    log_json TEXT NOT NULL DEFAULT '[]',
                    started_at TEXT NULL,
                    ends_at TEXT NULL,
                    snitch_unlocked_at TEXT NULL,
                    started_manually INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (fixture_id) REFERENCES quidditch_fixtures(id) ON DELETE CASCADE
                )
                """
            )
        else:
            live_match_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(quidditch_live_match_state)").fetchall()
            }
            if "started_manually" not in live_match_columns:
                conn.execute(
                    "ALTER TABLE quidditch_live_match_state "
                    "ADD COLUMN started_manually INTEGER NOT NULL DEFAULT 0"
                )

        if "quidditch_test_matches" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quidditch_test_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NULL,
                    message_id INTEGER NULL,
                    home_house TEXT NOT NULL,
                    away_house TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    log_json TEXT NOT NULL DEFAULT '[]',
                    image_path TEXT NULL,
                    started_at TEXT NOT NULL,
                    ends_at TEXT NOT NULL,
                    snitch_unlocked_at TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        if "quidditch_match_runtime_state" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quidditch_match_runtime_state (
                    match_scope TEXT NOT NULL,
                    match_id INTEGER NOT NULL,
                    state_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (match_scope, match_id)
                )
                """
            )

        if "quidditch_house_position_rotation" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quidditch_house_position_rotation (
                    guild_id INTEGER NOT NULL,
                    house_name TEXT NOT NULL,
                    position_key TEXT NOT NULL,
                    cycle_json TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, house_name, position_key)
                )
                """
            )

        if "quidditch_match_cheers" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quidditch_match_cheers (
                    match_scope TEXT NOT NULL,
                    match_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    cheering_house TEXT NOT NULL,
                    last_cheered_at TEXT NOT NULL,
                    cheer_count INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (match_scope, match_id, user_id)
                )
                """
            )

        if "house_monthly_bonus_points" not in existing_tables:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS house_monthly_bonus_points (
                    house_name TEXT NOT NULL,
                    year_month TEXT NOT NULL,
                    points INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (house_name, year_month)
                )
                """
            )

    def _ensure_indexes(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_media_posts_open_by_channel "
            "ON media_posts(channel_id, author_user_id, is_closed)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_media_posts_expiry "
            "ON media_posts(is_closed, closes_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_media_votes_window "
            "ON media_votes(voter_user_id, created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reaction_role_messages_message_id "
            "ON reaction_role_messages(message_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reaction_role_memberships_group "
            "ON reaction_role_memberships(guild_id, group_key, role_key)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quidditch_position_progress_user "
            "ON quidditch_position_progress(user_id, position_key)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quidditch_loop_control_guild "
            "ON quidditch_loop_control(guild_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quidditch_seasons_guild "
            "ON quidditch_seasons(guild_id, season_key)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quidditch_fixtures_season "
            "ON quidditch_fixtures(season_id, match_day)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quidditch_fixtures_status "
            "ON quidditch_fixtures(status, starts_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quidditch_standings_season "
            "ON quidditch_house_standings(season_id, house_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quidditch_test_matches_guild_status "
            "ON quidditch_test_matches(guild_id, status, started_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quidditch_runtime_scope "
            "ON quidditch_match_runtime_state(match_scope, match_id)"
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quidditch_rotation_guild "
            "ON quidditch_house_position_rotation(guild_id, house_name, position_key)"
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_quidditch_cheers_match "
            "ON quidditch_match_cheers(match_scope, match_id, cheering_house)"
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_house_monthly_bonus_points_month "
            "ON house_monthly_bonus_points(year_month, house_name)"
        )