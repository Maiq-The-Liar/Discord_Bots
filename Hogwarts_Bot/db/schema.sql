PRAGMA foreign_keys = ON;


CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    sickles_balance INTEGER NOT NULL DEFAULT 0,
    lifetime_house_points INTEGER NOT NULL DEFAULT 0,
    patronus_id TEXT NULL,
    bio TEXT NULL,
    birth_day INTEGER NULL,
    birth_month INTEGER NULL,
    xp INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 1,
    last_xp_at TEXT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventories (
    user_id INTEGER PRIMARY KEY,
    patronus_lessons INTEGER NOT NULL DEFAULT 0,
    chocolate_frogs INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_house_monthly_contributions (
    user_id INTEGER NOT NULL,
    house_name TEXT NOT NULL,
    year_month TEXT NOT NULL,
    points INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, house_name, year_month),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_role_snapshots (
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    role_name TEXT NOT NULL,
    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_role_sync_state (
    user_id INTEGER PRIMARY KEY,
    last_synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS bot_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS guild_role_mappings (
    guild_id INTEGER NOT NULL,
    role_key TEXT NOT NULL,
    role_id INTEGER NOT NULL,
    role_name TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, role_key)
);

CREATE TABLE IF NOT EXISTS user_owned_items (
    user_id INTEGER NOT NULL,
    item_key TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, item_key),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_chocolate_frog_cards (
    user_id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    first_discovered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, card_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS casual_quiz_channels (
    channel_id INTEGER PRIMARY KEY,
    is_active INTEGER NOT NULL DEFAULT 1,
    current_question_id INTEGER NULL,
    last_asked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quiz_question_history (
    channel_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    asked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (channel_id, question_id),
    FOREIGN KEY (channel_id) REFERENCES casual_quiz_channels(channel_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS birthday_announcements (
    message_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    birthday_user_id INTEGER NOT NULL,
    announcement_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS birthday_gift_claims (
    message_id INTEGER NOT NULL,
    giver_user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (message_id, giver_user_id),
    FOREIGN KEY (message_id) REFERENCES birthday_announcements(message_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS media_channels (
    channel_id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS media_posts (
    message_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    author_user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closes_at TEXT NOT NULL,
    is_closed INTEGER NOT NULL DEFAULT 0,
    reward_points_per_vote INTEGER NOT NULL DEFAULT 3,
    rewarded_points INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS media_votes (
    message_id INTEGER NOT NULL,
    voter_user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (message_id, voter_user_id),
    FOREIGN KEY (message_id) REFERENCES media_posts(message_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS media_vote_cooldowns (
    voter_user_id INTEGER PRIMARY KEY,
    last_vote_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guild_role_mappings (
    guild_id INTEGER NOT NULL,
    role_key TEXT NOT NULL,
    role_id INTEGER NOT NULL,
    role_name TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, role_key)
);

CREATE TABLE IF NOT EXISTS reaction_role_channels (
    guild_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reaction_role_messages (
    guild_id INTEGER NOT NULL,
    group_key TEXT NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, group_key)
);

CREATE TABLE IF NOT EXISTS reaction_role_memberships (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    group_key TEXT NOT NULL,
    role_key TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, user_id, group_key, role_key)
);