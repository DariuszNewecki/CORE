-- .intent/charter/schemas/data/agent_memory_schema.yaml implementation

CREATE TYPE agent_outcome AS ENUM ('success', 'failure', 'partial');

CREATE TABLE core.agent_episodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    context_packet_id UUID, -- Links to context_packets table
    outcome agent_outcome NOT NULL,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE core.agent_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_id UUID REFERENCES core.agent_episodes(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    reasoning_trace JSONB NOT NULL, -- Chain of thought
    tool_output_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE core.agent_reflections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic TEXT NOT NULL,
    insight TEXT NOT NULL,
    confidence_score FLOAT CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    source_episode_ids JSONB DEFAULT '[]'::jsonb, -- Array of UUIDs
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indices for retrieval
CREATE INDEX idx_episodes_task ON core.agent_episodes(task_id);
CREATE INDEX idx_reflections_topic ON core.agent_reflections(topic);
