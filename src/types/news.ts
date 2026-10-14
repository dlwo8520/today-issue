import { z } from 'zod';

const text = z.string().trim().min(1);
const instant = z.iso.datetime({ offset: true });
const source = z.object({
  id: text, publisher: text, title: text,
  url: z.url().refine(v => /^https?:\/\//.test(v)),
  publishedAt: instant, independenceKey: text, method: text,
  providers: z.array(text).optional().default([]),
  publisherKey: z.string().nullable().optional().default(null),
  imageUrl: z.url().refine(v => {
    try { const url = new URL(v); return /^https?:$/.test(url.protocol) && !url.username && !url.password; }
    catch { return false; }
  }).nullable().optional().default(null),
});
const statement = z.object({
  id: text, text, kind: z.enum(['fact', 'claim']),
  attribution: z.string().nullable(), sourceIds: z.array(text).min(1),
}).refine(v => v.kind !== 'claim' || Boolean(v.attribution?.trim()), '주장의 주체가 필요합니다.');
const issue = z.object({
  id: text, rank: z.number().int().min(1).max(6), title: text,
  oneLineSummary: text, titleSourceIds: z.array(text).min(1),
  summarySourceIds: z.array(text).min(1),
  background: z.array(statement), currentSituation: z.array(statement).min(1),
  response: z.array(statement),
  terminology: z.array(z.object({ term: text, explanation: text })),
  sources: z.array(source).min(1),
  ranking: z.object({
    method: z.enum(['demo', 'coverage_recency', 'engagement', 'headline_coverage']),
    score: z.number().finite().nullable(), reason: text,
    components: z.record(z.string(), z.number().nullable()),
    missingMetrics: z.array(z.string()),
  }),
}).superRefine((v, ctx) => {
  const ids = new Set(v.sources.map(s => s.id));
  if (ids.size !== v.sources.length) ctx.addIssue({ code: 'custom', message: '출처 ID 중복' });
  const references = [...v.titleSourceIds, ...v.summarySourceIds,
    ...[...v.background, ...v.currentSituation, ...v.response].flatMap(s => s.sourceIds)];
  if (references.some(id => !ids.has(id))) ctx.addIssue({ code: 'custom', message: '알 수 없는 출처' });
});
export const editionSchema = z.object({
  schemaVersion: z.literal(1), mode: z.enum(['demo', 'live']),
  date: z.iso.date(), updatedAt: instant, collectionStartedAt: instant,
  windowStart: instant, windowEnd: instant, timezone: z.literal('Asia/Seoul'),
  rankingMethod: z.enum(['demo', 'coverage_recency', 'engagement', 'mixed', 'headline_coverage']),
  publicationScope: z.enum(['public', 'local_private']).optional().default('public'),
  warnings: z.array(z.string()), issues: z.array(issue).max(6),
}).superRefine((v, ctx) => {
  if (new Set(v.issues.map(i => i.id)).size !== v.issues.length ||
      v.issues.some((i, n) => i.rank !== n + 1)) {
    ctx.addIssue({ code: 'custom', message: '이슈 ID 또는 순위 오류' });
  }
  if (v.mode === 'live' && (v.rankingMethod === 'demo' || v.issues.some(i => i.ranking.method === 'demo' || i.sources.some(s => s.method === 'demo')))) {
    ctx.addIssue({ code: 'custom', message: 'Live 데이터에 DEMO가 포함되어 있습니다.' });
  }
});
export const statusSchema = z.object({
  attemptedAt: instant, state: z.enum(['ok', 'error']), message: text,
});
export type Edition = z.infer<typeof editionSchema>;
export type Issue = Edition['issues'][number];
export type Statement = Issue['currentSituation'][number];
export type UpdateStatus = z.infer<typeof statusSchema>;
