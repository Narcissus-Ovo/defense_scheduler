/** Space-separated terms may match different columns of the same row. */
export function matchesListSearch(query: string, fields: unknown[]): boolean {
  const text = fields.flat().map(value => String(value ?? '')).join(' ').toLocaleLowerCase()
  return query.trim().toLocaleLowerCase().split(/\s+/).every(term => text.includes(term))
}
