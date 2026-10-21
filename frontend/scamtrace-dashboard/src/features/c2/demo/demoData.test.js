// Demo mode honesty: only recorded examples get a verdict, it keeps its real analysed date,
// and the bundled fixtures are v0.3 TEST pages (the export script refuses anything else).
import { describe, expect, it, vi } from 'vitest'
import analyses from '../fixtures/analyses.json'
import scans from '../fixtures/scans.json'
import stats from '../fixtures/stats.json'
import { DEMO_EXAMPLES, DEMO_NOTICE, DEMO_REPLAY_TOOLTIP, demoAnalyze, pickDemoAnalysis, replayRow } from './demoData.js'

describe('pickDemoAnalysis', () => {
  it('returns the recorded fixture for every demo example', () => {
    for (const example of DEMO_EXAMPLES) {
      expect(pickDemoAnalysis(analyses, example.input)).toBe(analyses[example.key])
    }
  })

  it('accepts the fanged / scheme-less / trailing-slash forms of an example', () => {
    expect(pickDemoAnalysis(analyses, 'https://digitalapexminingtech.com')).toBe(analyses.crypto_scam)
    expect(pickDemoAnalysis(analyses, '  DigitalApexMiningTech.com/ ')).toBe(analyses.crypto_scam)
    expect(pickDemoAnalysis(analyses, 'https://lankadeepa.lk/latest_news')).toBe(analyses.benign_sinhala)
  })

  it('never hands another page’s verdict to an unknown URL', () => {
    for (const input of ['https://my-crypto-coin.example/', 'https://example.com/', 'https://it-corp.netlify.app/', 'html', '', null]) {
      expect(pickDemoAnalysis(analyses, input)).toBeNull()
    }
  })
})

describe('demoAnalyze', () => {
  it('answers an unknown input at once with the notice (no fake delay, no verdict)', async () => {
    vi.useFakeTimers()
    try {
      const answer = await demoAnalyze('https://some-other-site.example/login')
      expect(answer).toEqual({ demo: true, notice: DEMO_NOTICE })
      expect(answer.notice).toBe('Demo mode: live scanning is off. Choose an example below, or turn Demo mode off to scan this URL.')
      expect(vi.getTimerCount()).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('keeps the original analyzed_at of a recorded example and marks it demo', async () => {
    vi.useFakeTimers()
    try {
      const pending = demoAnalyze(DEMO_EXAMPLES.find((example) => example.key === 'phishing').input)
      await vi.runAllTimersAsync()
      const answer = await pending
      expect(answer.demo).toBe(true)
      expect(answer.analyzed_at).toBe(analyses.phishing.analyzed_at)
      expect(answer.verdict).toBe('Malicious')
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('replayRow', () => {
  it('marks the row replayed, keeps the recorded time, stamps the replay time', () => {
    const item = scans.items[0]
    const at = new Date('2030-01-01T00:00:00Z')
    const row = replayRow(item, at)
    expect(row).toMatchObject({ id: item.id, demo: true, replayed: true, recorded_at: item.created_at, created_at: at.toISOString() })
    expect(replayRow(row, new Date()).recorded_at).toBe(item.created_at) // replaying again keeps it
    expect(DEMO_REPLAY_TOOLTIP).toBe('replayed from v0.3 test set')
  })
})

describe('bundled fixtures', () => {
  it('no longer contain the train-split Zimbra page', () => {
    expect(Object.values(analyses).map((analysis) => analysis.request_id)).not.toContain('c2_phishing_000081')
    expect(analyses.phishing_zimbra).toBeUndefined()
  })

  it('list full hosts with a hosted_on tag instead of merging into google.com', () => {
    const keys = stats['7d'].top_domains.map((domain) => domain.key)
    expect(keys).toContain('docs[.]google[.]com')
    expect(stats['7d'].top_domains.find((domain) => domain.key === 'docs[.]google[.]com').hosted_on).toBe('Google')
    expect(scans.items.every((item) => item.demo)).toBe(true)
  })
})
