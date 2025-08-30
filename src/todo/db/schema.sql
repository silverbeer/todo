-- Todo Application Database Schema
-- DuckDB SQL Schema for todo application

-- Categories table for task organization
CREATE SEQUENCE IF NOT EXISTS categories_id_seq;
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY DEFAULT nextval('categories_id_seq'),
    name VARCHAR(50) NOT NULL UNIQUE,
    color VARCHAR(7),  -- Hex color code #RRGGBB
    icon VARCHAR(2),   -- Single emoji or character
    description VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default categories
INSERT INTO categories (name, color, icon, description) VALUES
('Work', '#3B82F6', '💼', 'Work-related tasks and projects'),
('Personal', '#10B981', '👤', 'Personal tasks and activities'),
('Home', '#F59E0B', '🏠', 'Home maintenance and household tasks'),
('Health', '#EF4444', '❤️', 'Health and fitness activities'),
('Learning', '#8B5CF6', '📚', 'Learning and education'),
('Shopping', '#EC4899', '🛒', 'Shopping and errands'),
('Finance', '#059669', '💰', 'Financial tasks and planning')
ON CONFLICT(name) DO NOTHING;

-- Recurrence rules for recurring tasks
CREATE SEQUENCE IF NOT EXISTS recurrence_rules_id_seq;
CREATE TABLE IF NOT EXISTS recurrence_rules (
    id INTEGER PRIMARY KEY DEFAULT nextval('recurrence_rules_id_seq'),
    pattern VARCHAR(20) NOT NULL CHECK (pattern IN ('daily', 'weekly', 'monthly', 'yearly', 'custom')),
    interval_value INTEGER NOT NULL DEFAULT 1 CHECK (interval_value > 0),
    weekdays TEXT,  -- JSON array: [0,1,2,3,4] for Mon-Fri
    day_of_month INTEGER CHECK (day_of_month BETWEEN 1 AND 31),
    end_date DATE,
    max_occurrences INTEGER CHECK (max_occurrences > 0),
    next_due_date DATE,
    created_from_ai BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Main todos table
CREATE SEQUENCE IF NOT EXISTS todos_id_seq;
CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY DEFAULT nextval('todos_id_seq'),
    uuid VARCHAR(36) NOT NULL UNIQUE,  -- UUID for external references
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'archived')),

    -- Size and priority (user override vs AI suggested)
    user_override_size VARCHAR(10) CHECK (user_override_size IN ('small', 'medium', 'large')),
    ai_suggested_size VARCHAR(10) CHECK (ai_suggested_size IN ('small', 'medium', 'large')),
    final_size VARCHAR(10) NOT NULL DEFAULT 'medium'
        CHECK (final_size IN ('small', 'medium', 'large')),

    user_override_priority VARCHAR(10) CHECK (user_override_priority IN ('low', 'medium', 'high', 'urgent')),
    ai_suggested_priority VARCHAR(10) CHECK (ai_suggested_priority IN ('low', 'medium', 'high', 'urgent')),
    final_priority VARCHAR(10) NOT NULL DEFAULT 'medium'
        CHECK (final_priority IN ('low', 'medium', 'high', 'urgent')),

    -- Foreign keys
    category_id INTEGER REFERENCES categories(id),
    recurrence_rule_id INTEGER REFERENCES recurrence_rules(id),
    parent_todo_id INTEGER REFERENCES todos(id),  -- For recurring instances

    -- Time tracking
    estimated_minutes INTEGER CHECK (estimated_minutes > 0),
    actual_minutes INTEGER CHECK (actual_minutes > 0),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    due_date DATE,

    -- Gamification
    base_points INTEGER NOT NULL DEFAULT 0 CHECK (base_points >= 0),
    bonus_points INTEGER NOT NULL DEFAULT 0 CHECK (bonus_points >= 0),
    total_points_earned INTEGER NOT NULL DEFAULT 0 CHECK (total_points_earned >= 0),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure completed tasks have completion timestamp
    CHECK (status != 'completed' OR completed_at IS NOT NULL)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
CREATE INDEX IF NOT EXISTS idx_todos_category ON todos(category_id);
CREATE INDEX IF NOT EXISTS idx_todos_due_date ON todos(due_date);
CREATE INDEX IF NOT EXISTS idx_todos_created_at ON todos(created_at);
CREATE INDEX IF NOT EXISTS idx_todos_status_due ON todos(status, due_date);
CREATE INDEX IF NOT EXISTS idx_todos_uuid ON todos(uuid);

-- AI enrichments table
CREATE SEQUENCE IF NOT EXISTS ai_enrichments_id_seq;
CREATE TABLE IF NOT EXISTS ai_enrichments (
    id INTEGER PRIMARY KEY DEFAULT nextval('ai_enrichments_id_seq'),
    todo_id INTEGER NOT NULL REFERENCES todos(id),
    provider VARCHAR(20) NOT NULL CHECK (provider IN ('openai', 'anthropic')),
    model_name VARCHAR(50) NOT NULL,

    -- AI suggestions
    suggested_category VARCHAR(50),
    suggested_priority VARCHAR(10) CHECK (suggested_priority IN ('low', 'medium', 'high', 'urgent')),
    suggested_size VARCHAR(10) CHECK (suggested_size IN ('small', 'medium', 'large')),
    estimated_duration_minutes INTEGER CHECK (estimated_duration_minutes > 0),

    -- Recurrence detection
    is_recurring_candidate BOOLEAN DEFAULT FALSE,
    suggested_recurrence_pattern VARCHAR(100),

    -- AI reasoning and confidence
    reasoning TEXT,
    confidence_score REAL DEFAULT 0.5 CHECK (confidence_score BETWEEN 0.0 AND 1.0),

    -- Context
    context_keywords TEXT,  -- JSON array of keywords
    similar_tasks_found INTEGER DEFAULT 0 CHECK (similar_tasks_found >= 0),

    -- Performance tracking
    enriched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_time_ms INTEGER CHECK (processing_time_ms >= 0)
);

CREATE INDEX IF NOT EXISTS idx_ai_enrichments_todo ON ai_enrichments(todo_id);
CREATE INDEX IF NOT EXISTS idx_ai_enrichments_provider ON ai_enrichments(provider);

-- AI learning feedback table
CREATE SEQUENCE IF NOT EXISTS ai_learning_feedback_id_seq;
CREATE TABLE IF NOT EXISTS ai_learning_feedback (
    id INTEGER PRIMARY KEY DEFAULT nextval('ai_learning_feedback_id_seq'),
    original_task_text VARCHAR(500) NOT NULL,
    ai_provider VARCHAR(20) NOT NULL CHECK (ai_provider IN ('openai', 'anthropic')),

    -- Original AI suggestions
    ai_suggested_category VARCHAR(50),
    ai_suggested_size VARCHAR(10) CHECK (ai_suggested_size IN ('small', 'medium', 'large')),
    ai_suggested_priority VARCHAR(10) CHECK (ai_suggested_priority IN ('low', 'medium', 'high', 'urgent')),

    -- User corrections
    user_corrected_category VARCHAR(50),
    user_corrected_size VARCHAR(10) CHECK (user_corrected_size IN ('small', 'medium', 'large')),
    user_corrected_priority VARCHAR(10) CHECK (user_corrected_priority IN ('low', 'medium', 'high', 'urgent')),

    -- Learning context
    task_keywords TEXT,  -- JSON array
    correction_type VARCHAR(50) NOT NULL,  -- 'size_increase', 'size_decrease', 'category_change', etc.

    feedback_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_learning_feedback_provider ON ai_learning_feedback(ai_provider);
CREATE INDEX IF NOT EXISTS idx_learning_feedback_correction_type ON ai_learning_feedback(correction_type);

-- User statistics table
CREATE SEQUENCE IF NOT EXISTS user_stats_id_seq;
CREATE TABLE IF NOT EXISTS user_stats (
    id INTEGER PRIMARY KEY DEFAULT nextval('user_stats_id_seq'),

    -- Point tracking
    total_points INTEGER NOT NULL DEFAULT 0 CHECK (total_points >= 0),
    level INTEGER NOT NULL DEFAULT 1 CHECK (level >= 1),
    points_to_next_level INTEGER NOT NULL DEFAULT 100 CHECK (points_to_next_level >= 0),

    -- Task completion
    total_tasks_completed INTEGER NOT NULL DEFAULT 0 CHECK (total_tasks_completed >= 0),
    total_tasks_created INTEGER NOT NULL DEFAULT 0 CHECK (total_tasks_created >= 0),

    -- Streak tracking
    current_streak_days INTEGER NOT NULL DEFAULT 0 CHECK (current_streak_days >= 0),
    longest_streak_days INTEGER NOT NULL DEFAULT 0 CHECK (longest_streak_days >= 0),
    last_completion_date DATE,

    -- Goals
    daily_goal INTEGER NOT NULL DEFAULT 3 CHECK (daily_goal >= 1),
    weekly_goal INTEGER NOT NULL DEFAULT 20 CHECK (weekly_goal >= 1),
    monthly_goal INTEGER NOT NULL DEFAULT 80 CHECK (monthly_goal >= 1),

    -- Achievements
    achievements_unlocked INTEGER NOT NULL DEFAULT 0 CHECK (achievements_unlocked >= 0),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default user stats if not exists
INSERT INTO user_stats DEFAULT VALUES
ON CONFLICT DO NOTHING;

-- Daily activity tracking table
CREATE SEQUENCE IF NOT EXISTS daily_activity_id_seq;
CREATE TABLE IF NOT EXISTS daily_activity (
    id INTEGER PRIMARY KEY DEFAULT nextval('daily_activity_id_seq'),
    activity_date DATE NOT NULL UNIQUE,

    -- Task completion
    tasks_completed INTEGER NOT NULL DEFAULT 0 CHECK (tasks_completed >= 0),
    tasks_created INTEGER NOT NULL DEFAULT 0 CHECK (tasks_created >= 0),

    -- Points breakdown
    base_points_earned INTEGER NOT NULL DEFAULT 0 CHECK (base_points_earned >= 0),
    streak_bonus_earned INTEGER NOT NULL DEFAULT 0 CHECK (streak_bonus_earned >= 0),
    daily_goal_bonus_earned INTEGER NOT NULL DEFAULT 0 CHECK (daily_goal_bonus_earned >= 0),
    total_points_earned INTEGER NOT NULL DEFAULT 0 CHECK (total_points_earned >= 0),

    -- Goal achievement
    daily_goal_met BOOLEAN DEFAULT FALSE,
    streak_active BOOLEAN DEFAULT FALSE,

    -- Penalties
    overdue_penalty_applied INTEGER NOT NULL DEFAULT 0 CHECK (overdue_penalty_applied >= 0),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_daily_activity_date ON daily_activity(activity_date);

-- Achievements table
CREATE SEQUENCE IF NOT EXISTS achievements_id_seq;
CREATE TABLE IF NOT EXISTS achievements (
    id INTEGER PRIMARY KEY DEFAULT nextval('achievements_id_seq'),
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500) NOT NULL,
    icon VARCHAR(2),  -- Emoji

    -- Requirements
    requirement_type VARCHAR(50) NOT NULL,  -- 'tasks_completed', 'streak_days', 'points_earned'
    requirement_value INTEGER NOT NULL CHECK (requirement_value >= 1),
    bonus_points INTEGER NOT NULL DEFAULT 0 CHECK (bonus_points >= 0),

    -- User progress
    is_unlocked BOOLEAN DEFAULT FALSE,
    progress_current INTEGER NOT NULL DEFAULT 0 CHECK (progress_current >= 0),
    unlocked_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default achievements
INSERT INTO achievements (name, description, icon, requirement_type, requirement_value, bonus_points) VALUES
('First Steps', 'Complete your first task', '🎯', 'tasks_completed', 1, 10),
('Getting Started', 'Complete 10 tasks', '🚀', 'tasks_completed', 10, 25),
('Productive', 'Complete 50 tasks', '⚡', 'tasks_completed', 50, 50),
('Century Club', 'Complete 100 tasks', '💯', 'tasks_completed', 100, 100),
('Task Master', 'Complete 500 tasks', '👑', 'tasks_completed', 500, 250),
('Day One', 'Maintain a 1-day streak', '📅', 'streak_days', 1, 5),
('Week Warrior', 'Maintain a 7-day streak', '🔥', 'streak_days', 7, 35),
('Month Champion', 'Maintain a 30-day streak', '🏆', 'streak_days', 30, 150),
('Point Collector', 'Earn 1000 points', '💎', 'points_earned', 1000, 100),
('Point Master', 'Earn 5000 points', '💍', 'points_earned', 5000, 500)
ON CONFLICT(name) DO NOTHING;

-- Schema migrations tracking table
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
