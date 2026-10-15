export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export async function collectAllPages<T>(load: (page: number) => Promise<Page<T>>): Promise<Page<T>> {
  const first = await load(1)
  const pageSize = first.page_size
  if (pageSize < 1 || first.items.length >= first.total) return first

  const items = [...first.items]
  const totalPages = Math.ceil(first.total / pageSize)
  for (let page = 2; page <= totalPages; page += 1) {
    const next = await load(page)
    items.push(...next.items)
  }

  return { items, total: first.total, page: 1, page_size: pageSize }
}
