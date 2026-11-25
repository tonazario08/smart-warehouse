import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Pagination } from './Pagination'

describe('Pagination', () => {
  it('optionally localizes management controls without changing bounded navigation', () => {
    const change = vi.fn()
    const { rerender } = render(<Pagination locale="vi" page={1} pageSize={20} total={21} onPageChange={change} />)
    expect(screen.getByRole('navigation', { name: 'Phân trang' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Trang trước' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
    expect(change).toHaveBeenCalledWith(2)
    rerender(<Pagination locale="vi" page={1} pageSize={20} total={0} onPageChange={change} />)
    expect(screen.getByText('Chưa có trang')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Trang sau' })).toBeDisabled()
  })
  it('describes the current page and disables controls at both ends', () => {
    const onPageChange = vi.fn()
    render(<Pagination page={1} pageSize={20} total={40} onPageChange={onPageChange} />)

    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }))
    expect(onPageChange).toHaveBeenCalledWith(2)
  })

  it('disables next at the last page and handles an empty result set', () => {
    const onPageChange = vi.fn()
    const { rerender } = render(<Pagination page={2} pageSize={20} total={40} onPageChange={onPageChange} />)
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()

    rerender(<Pagination page={1} pageSize={20} total={0} onPageChange={onPageChange} />)
    expect(screen.getByText('No pages')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()
  })
})
