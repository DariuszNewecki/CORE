-- Minimal catalog tables for domains + capabilities (DB = SSOT)
create table if not exists core.domains (
  key          text primary key,
  title        text not null,
  description  text,
  parent_key   text references core.domains(key),
  status       text check (status in ('active','deprecated')) not null default 'active',
  last_seen_at timestamptz not null default now()
);

create table if not exists core.capabilities (
  key          text primary key,
  title        text not null,
  domain       text not null references core.domains(key) on update cascade,
  owner        text not null default 'unassigned',
  status       text check (status in ('active','deprecated')) not null default 'active',
  last_seen_at timestamptz not null default now()
);

create index if not exists idx_capabilities_domain on core.capabilities(domain);
