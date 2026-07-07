CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'intake',          -- intake|active|paused|done
  phase TEXT,                            -- discovery|validation|design|development|testing|pilot|production|monitoring|retirement
  owner TEXT,
  customer TEXT,
  objective TEXT,
  start_date TEXT,
  target_date TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS sprints (
  id INTEGER PRIMARY KEY,
  project_id INTEGER REFERENCES projects(id),
  name TEXT,
  goal TEXT,
  start_date TEXT,
  end_date TEXT,
  status TEXT DEFAULT 'planned'          -- planned|active|done
);

CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY,
  project_id INTEGER REFERENCES projects(id),
  sprint_id INTEGER REFERENCES sprints(id),
  title TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'todo',            -- todo|doing|blocked|done
  priority TEXT DEFAULT 'medium',        -- high|medium|low
  due_date TEXT,
  tags TEXT,
  source TEXT DEFAULT 'manual',          -- manual|compliance_gap|intake|issue|checklist
  source_ref TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS roadmap_items (
  id INTEGER PRIMARY KEY,
  project_id INTEGER REFERENCES projects(id),
  title TEXT NOT NULL,
  description TEXT,
  horizon TEXT DEFAULT 'now',            -- now|next|later
  status TEXT DEFAULT 'planned',         -- planned|in_progress|done|dropped
  order_index INTEGER DEFAULT 0,
  target_date TEXT
);

CREATE TABLE IF NOT EXISTS blockers (
  id INTEGER PRIMARY KEY,
  project_id INTEGER,
  task_id INTEGER,
  title TEXT NOT NULL,
  description TEXT,
  severity TEXT DEFAULT 'medium',        -- high|medium|low
  status TEXT DEFAULT 'open',            -- open|resolved
  raised_at TEXT DEFAULT (datetime('now')),
  resolved_at TEXT,
  resolution TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY,
  project_id INTEGER,
  title TEXT NOT NULL,
  context TEXT,
  options_considered TEXT,
  decision TEXT,
  rationale TEXT,
  status TEXT DEFAULT 'pending',         -- pending|decided|revisited
  decided_at TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS risks (
  id INTEGER PRIMARY KEY,
  project_id INTEGER,
  title TEXT NOT NULL,
  description TEXT,
  category TEXT,                         -- clinical|data|model|regulatory|privacy|security|operational|vendor|other
  likelihood INTEGER DEFAULT 3,          -- 1..5
  impact INTEGER DEFAULT 3,              -- 1..5
  score INTEGER GENERATED ALWAYS AS (likelihood * impact) STORED,
  mitigation TEXT,
  owner TEXT,
  status TEXT DEFAULT 'open'             -- open|mitigated|accepted|closed
);

CREATE TABLE IF NOT EXISTS checklist_templates (
  id INTEGER PRIMARY KEY,
  period TEXT NOT NULL,                  -- daily|weekly|monthly
  section TEXT,
  item_text TEXT NOT NULL,
  order_index INTEGER DEFAULT 0,
  active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS checklist_instances (
  id INTEGER PRIMARY KEY,
  period TEXT NOT NULL,
  period_key TEXT NOT NULL,              -- '2026-06-11' | '2026-W24' | '2026-06'
  project_id INTEGER,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(period, period_key, project_id)
);

CREATE TABLE IF NOT EXISTS checklist_items (
  id INTEGER PRIMARY KEY,
  instance_id INTEGER REFERENCES checklist_instances(id),
  template_id INTEGER,
  section TEXT,
  text TEXT NOT NULL,
  done INTEGER DEFAULT 0,
  done_at TEXT,
  note TEXT,
  order_index INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS issues (
  id INTEGER PRIMARY KEY,
  project_id INTEGER,
  title TEXT NOT NULL,
  description TEXT,
  severity TEXT DEFAULT 'P2',            -- P0|P1|P2|P3
  status TEXT DEFAULT 'open',            -- open|investigating|mitigated|resolved|closed
  affected_area TEXT,
  reported_by TEXT,
  detected_at TEXT DEFAULT (datetime('now')),
  root_cause_category TEXT,              -- data|model|integration|workflow|people|external
  root_cause_detail TEXT,
  mitigation TEXT,
  resolution TEXT,
  closure_criteria TEXT,                 -- JSON [{"text":..., "done":0}]
  ai_recommendation TEXT,
  closed_at TEXT
);

CREATE TABLE IF NOT EXISTS kb_chapters (
  id INTEGER PRIMARY KEY,
  number INTEGER UNIQUE,
  title TEXT NOT NULL,
  summary TEXT,
  word_count INTEGER
);

CREATE TABLE IF NOT EXISTS kb_sections (
  id INTEGER PRIMARY KEY,
  chapter_id INTEGER REFERENCES kb_chapters(id),
  heading TEXT,
  level INTEGER DEFAULT 2,
  order_index INTEGER DEFAULT 0,
  content TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(
  heading, content,
  content='kb_sections', content_rowid='id',
  tokenize='porter'
);

CREATE TRIGGER IF NOT EXISTS kb_sections_ai AFTER INSERT ON kb_sections BEGIN
  INSERT INTO kb_fts(rowid, heading, content) VALUES (new.id, new.heading, new.content);
END;
CREATE TRIGGER IF NOT EXISTS kb_sections_ad AFTER DELETE ON kb_sections BEGIN
  INSERT INTO kb_fts(kb_fts, rowid, heading, content) VALUES ('delete', old.id, old.heading, old.content);
END;
CREATE TRIGGER IF NOT EXISTS kb_sections_au AFTER UPDATE ON kb_sections BEGIN
  INSERT INTO kb_fts(kb_fts, rowid, heading, content) VALUES ('delete', old.id, old.heading, old.content);
  INSERT INTO kb_fts(rowid, heading, content) VALUES (new.id, new.heading, new.content);
END;

CREATE TABLE IF NOT EXISTS glossary (
  id INTEGER PRIMARY KEY,
  term TEXT UNIQUE NOT NULL,
  definition TEXT,
  chapter_id INTEGER
);

CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY,
  project_id INTEGER,
  filename TEXT,
  mime TEXT,
  text TEXT,
  uploaded_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS compliance_rules (
  id INTEGER PRIMARY KEY,
  artifact_key TEXT UNIQUE,
  name TEXT,
  category TEXT,                         -- critical|important|standard
  weight INTEGER,
  keywords TEXT,                         -- JSON array of phrase variants
  heading_regex TEXT,
  recommendation TEXT,
  kb_query TEXT
);

CREATE TABLE IF NOT EXISTS compliance_reports (
  id INTEGER PRIMARY KEY,
  project_id INTEGER,
  document_id INTEGER,
  score INTEGER,
  max_score INTEGER,
  grade TEXT,                            -- Ready|Conditional|Needs Work|Not Ready
  summary TEXT,
  ai_enhanced INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS compliance_findings (
  id INTEGER PRIMARY KEY,
  report_id INTEGER REFERENCES compliance_reports(id),
  rule_id INTEGER REFERENCES compliance_rules(id),
  status TEXT,                           -- present|partial|missing
  evidence_snippet TEXT,
  gap_note TEXT,
  recommendation TEXT,
  kb_chapter_ids TEXT,                   -- JSON [3, 14]
  task_id INTEGER
);

CREATE TABLE IF NOT EXISTS agent_events (
  id INTEGER PRIMARY KEY,
  agent TEXT NOT NULL,                   -- execution|knowledge|compliance|orchestrator
  action TEXT NOT NULL,
  entity_type TEXT,
  entity_id INTEGER,
  summary TEXT,
  payload TEXT,                          -- JSON
  created_at TEXT DEFAULT (datetime('now'))
);
