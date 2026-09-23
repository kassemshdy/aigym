import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Field, Input, Segmented } from '@/components/ui/Field'
import { Icon } from '@/components/ui/Icon'
import { Empty, Page } from '@/components/ui/Page'
import { commitMemberImport, listPlans, previewMemberImport } from '@/data/queries'
import { useAsync } from '@/data/useAsync'
import { ApiError } from '@/data/client'
import { text } from '@/lib/format'
import type { ApiImportPreview, ApiImportRow, CommitImportRow } from '@/data/types'
import type { Lang } from '@/i18n'

/**
 * Bringing a gym's notebook in. File picker, then a row-per-card editor
 * for whatever came back broken, then one commit.
 *
 * **Nothing here parses a CSV.** The file goes straight to the server,
 * which hands back rows already normalized — phone numbers in one shape,
 * dates read day-first, Arabic decoded whichever way Excel wrote it. That
 * is the point of app/domain/csv_import.py: a preview the browser parsed
 * and a commit the server validated would be two implementations of the
 * same rules, and the manager would be approving one while the other did
 * the writing.
 *
 * Rows that came back clean are shown as one compact line each, because
 * they came out of the gym's own file and there is nothing to decide. The
 * full editor is reserved for rows that cannot be imported yet, so the
 * work on screen is proportional to what is actually wrong.
 */
export function ManagerImport() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language as Lang
  const fileRef = useRef<HTMLInputElement>(null)

  const plans = useAsync(listPlans, [])
  const [defaultPlanId, setDefaultPlanId] = useState<string | null>(null)
  const [preview, setPreview] = useState<ApiImportPreview | null>(null)
  const [rows, setRows] = useState<ApiImportRow[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [imported, setImported] = useState<number | null>(null)

  const planId = defaultPlanId ?? plans.data?.[0]?.id ?? null

  function reset() {
    setPreview(null)
    setRows([])
    setError(null)
    setImported(null)
  }

  function update(line: number, patch: Partial<ApiImportRow>) {
    setRows((current) =>
      current.map((row) =>
        row.line === line
          ? // Errors are cleared as soon as the row is touched: the server
            // re-checks every one of them on commit, so keeping a stale
            // "phone_invalid" next to a number the manager has just fixed
            // would only argue with them.
            { ...row, ...patch, errors: [] }
          : row,
      ),
    )
  }

  function removeRow(line: number) {
    setRows((current) => current.filter((row) => row.line !== line))
  }

  async function choose(file: File) {
    setBusy(true)
    setError(null)
    try {
      const result = await previewMemberImport(file, planId)
      setPreview(result)
      setRows(result.rows)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  const ready = rows.filter((r) => r.errors.length === 0 && r.name.trim() && r.phone.trim() && r.plan_id)
  const blocked = rows.filter((r) => !ready.includes(r))

  async function commit() {
    setBusy(true)
    setError(null)
    try {
      const payload: CommitImportRow[] = ready.map((r) => ({
        line: r.line,
        name: r.name.trim(),
        // Both columns are NOT NULL on the server; a file with no English
        // column falls back the same way the parser does.
        name_en: (r.name_en || r.name).trim(),
        phone: r.phone.trim(),
        plan_id: r.plan_id as string,
        ends_at: r.ends_at,
      }))
      const result = await commitMemberImport(payload)
      setImported(result.imported)
      setPreview(null)
      setRows([])
    } catch (err) {
      // The server refuses the whole batch rather than importing part of
      // it, so its message names the line to go back to.
      setError(err instanceof ApiError ? err.message : t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  const planOptions = (plans.data ?? []).map((p) => ({
    value: p.id,
    label: text(p.name, lang),
  }))

  if (imported !== null) {
    return (
      <Page title={t('manager.import.title')}>
        <Card className="space-y-3 p-6 text-center">
          <span className="bg-paid-bg text-paid mx-auto flex size-12 items-center justify-center rounded-full">
            <Icon name="check" size={24} />
          </span>
          <p className="font-bold">{t('manager.import.done', { count: imported })}</p>
          <Button variant="secondary" full onClick={reset}>
            {t('common.done')}
          </Button>
        </Card>
      </Page>
    )
  }

  return (
    <Page title={t('manager.import.title')} sub={t('manager.import.sub')}>
      {preview === null ? (
        <Card className="space-y-4 p-4">
          <p className="text-muted text-sm">{t('manager.import.what')}</p>
          {planOptions.length > 0 ? (
            <Field label={t('manager.import.defaultPlan')}>
              <Segmented
                value={planId ?? planOptions[0].value}
                onChange={setDefaultPlanId}
                columns={2}
                options={planOptions}
              />
            </Field>
          ) : null}
          <p className="text-muted text-xs">{t('manager.import.defaultPlanNote')}</p>
          <Button variant="brand" full size="lg" disabled={busy} onClick={() => fileRef.current?.click()}>
            <Icon name="add" size={18} />
            {t('manager.import.choose')}
          </Button>
          {error ? (
            <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">{error}</p>
          ) : null}
        </Card>
      ) : null}

      <input
        ref={fileRef}
        type="file"
        accept=".csv,text/csv"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) void choose(file)
          e.target.value = ''
        }}
      />

      {preview && preview.missing_columns.length > 0 ? (
        <Card className="space-y-3 p-4">
          {/* Refusing beats guessing: picking the wrong column is how a
              gym imports 300 members under someone else's numbers. */}
          <p className="font-semibold">{t('manager.import.missingColumns')}</p>
          <p className="text-muted text-sm">
            {preview.missing_columns.map((c) => t(`manager.import.column.${c}`, c)).join('، ')}
          </p>
          <Button variant="secondary" full onClick={reset}>
            {t('common.cancel')}
          </Button>
        </Card>
      ) : null}

      {preview && rows.length > 0 ? (
        <>
          <Card className="p-4">
            <p className="font-semibold">
              {t('manager.import.summary', { ready: ready.length, blocked: blocked.length })}
            </p>
            {preview.truncated ? (
              <p className="text-muted mt-1 text-xs">{t('manager.import.truncated')}</p>
            ) : null}
          </Card>

          {blocked.length > 0 ? (
            <Card>
              <CardTitle>{t('manager.import.needsFixing')}</CardTitle>
              <div className="space-y-3 p-4">
                {blocked.map((row) => (
                  <div key={row.line} className="border-line space-y-3 rounded-xl border p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="tnum text-sm font-semibold">
                        <bdi>{t('manager.import.line', { n: row.line })}</bdi>
                      </span>
                      <button
                        type="button"
                        onClick={() => removeRow(row.line)}
                        aria-label={t('manager.import.skipRow')}
                        className="text-muted flex size-11 items-center justify-center"
                      >
                        <Icon name="close" size={18} />
                      </button>
                    </div>
                    {row.errors.length > 0 ? (
                      <ul className="text-muted space-y-1 text-xs">
                        {row.errors.map((code) => (
                          <li key={code}>{t(`manager.import.error.${code}`, code)}</li>
                        ))}
                      </ul>
                    ) : null}
                    <Field label={t('manager.staff.name')}>
                      <Input
                        value={row.name}
                        onChange={(e) => update(row.line, { name: e.target.value })}
                      />
                    </Field>
                    <Field label={t('manager.staff.phone')}>
                      <Input
                        value={row.phone}
                        onChange={(e) => update(row.line, { phone: e.target.value })}
                        inputMode="tel"
                        dir="ltr"
                        placeholder="+961 70 000 000"
                      />
                    </Field>
                    {planOptions.length > 0 ? (
                      <Field label={t('manager.import.plan')}>
                        <Segmented
                          value={row.plan_id ?? ''}
                          onChange={(v) => update(row.line, { plan_id: v })}
                          columns={2}
                          options={planOptions}
                        />
                      </Field>
                    ) : null}
                  </div>
                ))}
              </div>
            </Card>
          ) : null}

          {ready.length > 0 ? (
            <Card>
              <CardTitle>{t('manager.import.readyToAdd')}</CardTitle>
              <ul>
                {ready.map((row) => (
                  <li
                    key={row.line}
                    className="border-line flex items-center gap-3 border-b px-4 py-3 last:border-0"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-semibold">{row.name}</span>
                      <span className="text-muted tnum block text-xs" dir="ltr">
                        {row.phone}
                      </span>
                    </span>
                    <button
                      type="button"
                      onClick={() => removeRow(row.line)}
                      aria-label={t('manager.import.skipRow')}
                      className="text-muted flex size-11 items-center justify-center"
                    >
                      <Icon name="close" size={18} />
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          {error ? (
            <p className="bg-ink rounded-xl px-4 py-3 text-sm font-semibold text-white">{error}</p>
          ) : null}

          <div className="flex gap-2">
            <Button variant="secondary" size="lg" onClick={reset}>
              {t('common.cancel')}
            </Button>
            <Button
              full
              size="lg"
              disabled={busy || ready.length === 0}
              onClick={() => void commit()}
            >
              {t('manager.import.add', { count: ready.length })}
            </Button>
          </div>
        </>
      ) : null}

      {preview && rows.length === 0 && preview.missing_columns.length === 0 ? (
        <Empty>{t('manager.import.emptyFile')}</Empty>
      ) : null}
    </Page>
  )
}
