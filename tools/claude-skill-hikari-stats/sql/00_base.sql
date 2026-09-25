-- ひかりアプリ集計の「共通の下ごしらえ」。01〜05 の先頭にこれと同じ内容が入っている。
-- 自由質問用のSQLを組むときは、この with 句をそのまま使い、最後の select だけ書き換える。
-- 読むだけ。app_data への書き込み・設定変更は一切しない。
--
-- データの置き場所（index.html の loadJiageRows / _mergeJiageWithCards と同じ読み方）
--   ・地上げピン = app_data の id='jiage::<ピンid>' の行。data = { v:1, item:<ピン丸ごと> }
--   ・削除済み   = app_data id='hikari_main' の data.tombstones.jiage[<ピンid>] が正の数
--   ・個人保有   = item.personalOwner が入っているもの（会社の数字から外す＝companyOnly と同じ）
--
-- 段階（stage）は HANDOFF.md「5状態判定ロジック」と同じ優先順位。
-- 週は JST の月曜0時始まり（week_start_jst）。
with tomb as (
  select coalesce(data->'tombstones'->'jiage', '{}'::jsonb) as t
  from app_data where id = 'hikari_main'
),
raw as (
  select r.data->'item' as j
  from app_data r
  where r.id like 'jiage::%' and jsonb_typeof(r.data->'item') = 'object'
),
pins as (
  select
    j,
    j->>'id' as pin_id,
    coalesce(nullif(trim(j->>'assignee'), ''), '(未設定)') as assignee,
    coalesce(nullif(trim(j->>'area'), ''), '(未設定)') as area,
    coalesce(nullif(trim(j->>'status'), ''), '(未設定)') as status,
    coalesce(j->>'dm', '') as dm,
    coalesce(nullif(trim(j->>'address'), ''), '') as address,
    coalesce(nullif(trim(j->>'landmark'), ''), '') as landmark,
    coalesce(nullif(trim(j->>'owner'), ''), nullif(trim(j->>'ownerName'), ''), '') as owner,
    nullif(trim(j->>'address'), '') is not null as has_addr,
    (nullif(trim(j->>'owner'), '') is not null or nullif(trim(j->>'ownerName'), '') is not null) as has_owner,
    nullif(trim(j->>'ownerAddr'), '') is not null as has_owner_addr,
    coalesce(j->>'coordsManual', '') = 'true' as coords_manual,
    coalesce(j->>'excluded', '') = 'true' as excluded,
    coalesce(j->>'lookupFailed', '') = 'true' as lookup_failed,
    coalesce(j->>'lookupGiveUp', '') = 'true' as lookup_giveup,
    (select count(*) from jsonb_array_elements(case when jsonb_typeof(j->'dmLog') = 'array' then j->'dmLog' else '[]'::jsonb end) e
      where e->>'t' = '送付') as dm_log_sent,
    exists (select 1 from jsonb_array_elements(case when jsonb_typeof(j->'dmLog') = 'array' then j->'dmLog' else '[]'::jsonb end) e
      where e->>'t' in ('不要', '反応', '返送')) as dm_stopped,
    case
      when jsonb_typeof(j->'createdAt') = 'number' then to_timestamp((j->>'createdAt')::numeric / 1000)
      when j->>'createdAt' ~ '^\d{12,}$' then to_timestamp((j->>'createdAt')::numeric / 1000)
      when j->>'createdAt' ~ '^\d{4}-\d{2}-\d{2}' then (j->>'createdAt')::timestamptz
      when j->>'id' ~ '^\d{12,}$' then to_timestamp((j->>'id')::numeric / 1000)
    end as created_at,
    case
      when jsonb_typeof(j->'updatedAt') = 'number' then to_timestamp((j->>'updatedAt')::numeric / 1000)
      when j->>'updatedAt' ~ '^\d{12,}$' then to_timestamp((j->>'updatedAt')::numeric / 1000)
      when j->>'updatedAt' ~ '^\d{4}-\d{2}-\d{2}' then (j->>'updatedAt')::timestamptz
    end as updated_at
  from raw left join tomb on true
  where coalesce(trim(j->>'personalOwner'), '') = ''
    and not coalesce(case when tomb.t->>(j->>'id') ~ '^-?\d+(\.\d+)?$' then (tomb.t->>(j->>'id'))::numeric > 0 end, false)
),
p as (
  select *,
    case
      when not coords_manual then 'その他(取込ピン)'
      when not has_addr then '🟡地番待ち'
      when has_owner then '🚪訪問OK'
      when excluded then '🚫対象外'
      when lookup_giveup then '🛑取れない'
      when lookup_failed then '🔧要修正'
      else '⏳謄本待ち'
    end as stage,
    greatest(dm_log_sent, case dm when '①' then 1 when '②' then 2 when '済' then 1 else 0 end) as dm_sent,
    (date_trunc('week', now() at time zone 'Asia/Tokyo')) at time zone 'Asia/Tokyo' as week_start
  from pins
)
select count(*) as pins from p;
