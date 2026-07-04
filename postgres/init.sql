-- Brand Identity Search Engine Schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- trigram similarity for fuzzy search

-- ── Searches ────────────────────────────────────────────────────────
CREATE TABLE searches (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query       TEXT NOT NULL,
    results     JSONB,
    duration_ms INTEGER,
    ip_address  INET,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_searches_query    ON searches (query);
CREATE INDEX idx_searches_created  ON searches (created_at DESC);
CREATE INDEX idx_searches_query_trgm ON searches USING gin (query gin_trgm_ops);

-- ── Username Cache ───────────────────────────────────────────────────
CREATE TABLE username_results (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username    TEXT NOT NULL,
    platform    TEXT NOT NULL,
    available   BOOLEAN,
    url         TEXT,
    checked_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ DEFAULT NOW() + INTERVAL '1 hour',
    UNIQUE (username, platform)
);

CREATE INDEX idx_username_results_username ON username_results (username);
CREATE INDEX idx_username_results_expires  ON username_results (expires_at);

-- ── Trending Usernames ───────────────────────────────────────────────
CREATE TABLE trending (
    id          SERIAL PRIMARY KEY,
    username    TEXT UNIQUE NOT NULL,
    search_count INTEGER DEFAULT 1,
    last_searched TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_trending_count ON trending (search_count DESC);

-- ── Analytics Events ─────────────────────────────────────────────────
CREATE TABLE analytics_events (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type  TEXT NOT NULL,   -- 'search', 'autocomplete', 'platform_check'
    payload     JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_analytics_type    ON analytics_events (event_type);
CREATE INDEX idx_analytics_created ON analytics_events (created_at DESC);

-- ── Platform Definitions ─────────────────────────────────────────────
CREATE TABLE platforms (
    id          SERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    check_url   TEXT NOT NULL,
    icon        TEXT,
    category    TEXT,   -- 'social', 'dev', 'domain', 'gaming'
    active      BOOLEAN DEFAULT TRUE
);

INSERT INTO platforms (name, check_url, icon, category) VALUES
    ('GitHub',    'https://github.com/{username}',          '🐙', 'dev'),
    ('Instagram', 'https://instagram.com/{username}',       '📸', 'social'),
    ('Twitter',   'https://twitter.com/{username}',         '🐦', 'social'),
    ('Reddit',    'https://reddit.com/u/{username}',        '🤖', 'social'),
    ('TikTok',    'https://tiktok.com/@{username}',         '🎵', 'social'),
    ('YouTube',   'https://youtube.com/@{username}',        '▶️',  'social'),
    ('LinkedIn',  'https://linkedin.com/in/{username}',     '💼', 'social'),
    ('Twitch',    'https://twitch.tv/{username}',           '🎮', 'gaming'),
    ('Pinterest', 'https://pinterest.com/{username}',       '📌', 'social'),
    ('Medium',    'https://medium.com/@{username}',         '✍️',  'dev'),
    ('Dev.to',    'https://dev.to/{username}',              '💻', 'dev'),
    ('Telegram',  'https://t.me/{username}',                '✈️',  'social'),
    ('Discord',   'https://discord.com/users/{username}',   '💬', 'gaming'),
    ('Snapchat',  'https://snapchat.com/add/{username}',    '👻', 'social'),
    ('Behance',   'https://behance.net/{username}',         '🎨', 'creative'),
    ('Dribbble',  'https://dribbble.com/{username}',        '🏀', 'creative'),
    ('GitLab',    'https://gitlab.com/{username}',          '🦊', 'dev'),
    ('npm',       'https://www.npmjs.com/~{username}',      '📦', 'dev'),
    ('PyPI',      'https://pypi.org/user/{username}',       '🐍', 'dev'),
    ('HackerNews','https://news.ycombinator.com/user?id={username}', '🔶', 'dev');
