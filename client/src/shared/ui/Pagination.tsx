interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const pageCount = pageSize > 0 ? Math.ceil(total / pageSize) : 0
  const currentPage = pageCount === 0 ? 0 : Math.min(Math.max(page, 1), pageCount)

  return (
    <nav className="pagination" aria-label="Pagination">
      <button type="button" className="quiet" onClick={() => onPageChange(currentPage - 1)} disabled={currentPage <= 1}>
        Previous page
      </button>
      <span aria-live="polite">{pageCount === 0 ? 'No pages' : `Page ${currentPage} of ${pageCount}`}</span>
      <button type="button" className="quiet" onClick={() => onPageChange(currentPage + 1)} disabled={currentPage === 0 || currentPage >= pageCount}>
        Next page
      </button>
    </nav>
  )
}
