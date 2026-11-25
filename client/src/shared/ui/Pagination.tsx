interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
  locale?: 'en' | 'vi'
}

export function Pagination({ page, pageSize, total, onPageChange, locale = 'en' }: PaginationProps) {
  const pageCount = pageSize > 0 ? Math.ceil(total / pageSize) : 0
  const currentPage = pageCount === 0 ? 0 : Math.min(Math.max(page, 1), pageCount)

  return (
    <nav className="pagination" aria-label={locale === 'vi' ? 'Phân trang' : 'Pagination'}>
      <button type="button" className="quiet" onClick={() => onPageChange(currentPage - 1)} disabled={currentPage <= 1}>
        {locale === 'vi' ? 'Trang trước' : 'Previous page'}
      </button>
      <span aria-live="polite">{pageCount === 0 ? locale === 'vi' ? 'Chưa có trang' : 'No pages' : locale === 'vi' ? `Trang ${currentPage} / ${pageCount}` : `Page ${currentPage} of ${pageCount}`}</span>
      <button type="button" className="quiet" onClick={() => onPageChange(currentPage + 1)} disabled={currentPage === 0 || currentPage >= pageCount}>
        {locale === 'vi' ? 'Trang sau' : 'Next page'}
      </button>
    </nav>
  )
}
